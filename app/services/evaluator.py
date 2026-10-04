"""
Evaluator Service — Quality metrics and evaluation harness for Lead Enrichment.

Metrics:
  - Fill Rate: Percentage of core enrichment fields populated with non-null values.
  - Format Error Rate: Percentage of fields violating format standards (e.g., placeholder strings).
  - Ground-Truth Accuracy: Precision/recall against golden fixtures.
  - Guardrail Coverage: 100% of sub-threshold confidence runs flagged as needs_review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CORE_ENRICHMENT_FIELDS = [
    "company_name",
    "ceo_name",
    "ceo_email",
    "company_description",
    "linkedin_url",
    "linkedin_company_url",
    "employee_count",
    "company_website",
    "funding_raised",
    "industry",
    "founding_year",
    "news_articles",
]

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*\.[^\s]+", re.IGNORECASE)
_SUSPECT_PLACEHOLDERS = {"n/a", "not available", "unknown", "none", "null", "tbd", "pending"}


@dataclass
class QualityMetrics:
    total_cases: int = 0
    passed_cases: int = 0
    avg_fill_rate: float = 0.0
    format_error_rate: float = 0.0
    guardrail_accuracy: float = 1.0
    hallucination_violations: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.avg_fill_rate >= 0.75
            and self.format_error_rate <= 0.05
            and self.guardrail_accuracy == 1.0
            and self.hallucination_violations == 0
            and len(self.failures) == 0
        )


def compute_fill_rate(
    enriched_data: dict[str, Any],
    target_fields: list[str] | None = None,
) -> float:
    """Calculate the ratio of populated fields over the target field set."""
    fields = target_fields or CORE_ENRICHMENT_FIELDS
    if not fields:
        return 0.0

    populated = 0
    for f in fields:
        val = enriched_data.get(f)
        if val is not None and val != "" and val != []:
            populated += 1

    return populated / len(fields)


def compute_format_errors(enriched_data: dict[str, Any]) -> list[str]:
    """Identify any malformed or placeholder strings that escaped validation."""
    errors: list[str] = []

    # Check for placeholder strings in any field
    for k, v in enriched_data.items():
        if isinstance(v, str) and v.strip().lower() in _SUSPECT_PLACEHOLDERS:
            errors.append(f"{k} has suspect placeholder value: '{v}'")

    # Email format check
    email = enriched_data.get("ceo_email")
    if email and isinstance(email, str) and not _EMAIL_PATTERN.match(email.strip()):
        errors.append(f"Invalid email format: '{email}'")

    # Website format check
    website = enriched_data.get("company_website")
    if website and isinstance(website, str) and not _URL_PATTERN.match(website.strip()):
        errors.append(f"Invalid website URL format: '{website}'")

    return errors


def evaluate_single_lead(
    enriched_data: dict[str, Any],
    lead_status: str,
    expected_case: dict[str, Any],
) -> list[str]:
    """Check a single lead enrichment output against expected quality criteria."""
    issues: list[str] = []
    case_id = expected_case.get("id", "unknown")
    expected = expected_case.get("expected", {})

    # Status check
    expected_status = expected.get("status")
    if expected_status and lead_status != expected_status:
        issues.append(f"[{case_id}] Expected status={expected_status}, got={lead_status}")

    # Specific field checks
    for field_name in ["ceo_name", "ceo_email", "company_website", "founding_year"]:
        if field_name in expected:
            actual = enriched_data.get(field_name)
            expected_val = expected[field_name]
            if actual != expected_val:
                issues.append(f"[{case_id}] Field {field_name} mismatch: expected {expected_val!r}, got {actual!r}")

    # Min confidence check
    min_conf = expected.get("min_confidence")
    actual_conf = enriched_data.get("fallback_confidence_score")
    if min_conf is not None and actual_conf is not None:
        if actual_conf < min_conf:
            issues.append(f"[{case_id}] Confidence {actual_conf:.2f} < min {min_conf:.2f}")

    # Format errors
    fmt_errors = compute_format_errors(enriched_data)
    if fmt_errors:
        issues.extend([f"[{case_id}] Format error: {e}" for e in fmt_errors])

    # Hallucination guard: high confidence with no sources
    sources = enriched_data.get("fallback_sources_used", [])
    if actual_conf is not None and actual_conf >= 0.5 and len(sources) == 0:
        issues.append(f"[{case_id}] Hallucination rule violated: confidence {actual_conf} without sources")

    return issues


def evaluate_batch(
    runs: list[tuple[dict[str, Any], str, dict[str, Any]]],
) -> QualityMetrics:
    """Evaluate a batch of enrichment runs.

    Args:
        runs: List of (enriched_data, lead_status, expected_case) tuples.
    """
    total = len(runs)
    if total == 0:
        return QualityMetrics()

    all_fill_rates: list[float] = []
    total_fields_checked = 0
    total_format_errors = 0
    low_conf_flagged = 0
    total_low_conf = 0
    hallucination_violations = 0
    all_failures: list[str] = []

    for enriched_data, lead_status, expected_case in runs:
        fill_rate = compute_fill_rate(enriched_data)
        all_fill_rates.append(fill_rate)

        # Count format errors
        fmt_errors = compute_format_errors(enriched_data)
        total_format_errors += len(fmt_errors)
        total_fields_checked += len(CORE_ENRICHMENT_FIELDS)

        # Check guardrail consistency
        conf = enriched_data.get("fallback_confidence_score")
        if conf is not None and conf < 0.3:
            total_low_conf += 1
            if lead_status == "needs_review":
                low_conf_flagged += 1

        # Check hallucination
        sources = enriched_data.get("fallback_sources_used", [])
        if conf is not None and conf >= 0.5 and len(sources) == 0:
            hallucination_violations += 1

        issues = evaluate_single_lead(enriched_data, lead_status, expected_case)
        if issues:
            all_failures.extend(issues)

    avg_fill_rate = sum(all_fill_rates) / total if total > 0 else 0.0
    format_error_rate = total_format_errors / total_fields_checked if total_fields_checked > 0 else 0.0
    guardrail_accuracy = (low_conf_flagged / total_low_conf) if total_low_conf > 0 else 1.0

    passed_count = total - len({f.split("]")[0] for f in all_failures})

    return QualityMetrics(
        total_cases=total,
        passed_cases=max(0, passed_count),
        avg_fill_rate=avg_fill_rate,
        format_error_rate=format_error_rate,
        guardrail_accuracy=guardrail_accuracy,
        hallucination_violations=hallucination_violations,
        failures=all_failures,
    )
