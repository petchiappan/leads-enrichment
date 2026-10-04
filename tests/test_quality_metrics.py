"""
Quality gate & metric assertions for Lead Enrichment evaluation.

Validates that:
  - fill_rate calculation handles empty, partial, and full datasets
  - format_error_rate detects placeholder values and bad formats
  - hallucination rule catches high-confidence predictions with 0 sources
  - guardrail consistency confirms 100% of low-confidence cases get flagged
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.services.evaluator import (
    compute_fill_rate,
    compute_format_errors,
    evaluate_batch,
    evaluate_single_lead,
)

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "golden_leads.json"


@pytest.fixture()
def golden_dataset():
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestFillRateMetrics:
    def test_empty_dataset_has_zero_fill_rate(self):
        assert compute_fill_rate({}) == 0.0

    def test_full_dataset_has_one_hundred_percent(self):
        full_data = {
            "company_name": "Acme",
            "ceo_name": "Alice",
            "ceo_email": "alice@acme.com",
            "company_description": "Tech",
            "linkedin_url": "https://linkedin.com/in/alice",
            "linkedin_company_url": "https://linkedin.com/company/acme",
            "employee_count": 100,
            "company_website": "https://acme.com",
            "funding_raised": "$5M",
            "industry": "Software",
            "founding_year": 2020,
            "news_articles": ["Article 1"],
        }
        assert compute_fill_rate(full_data) == 1.0

    def test_partial_fill_rate(self):
        partial_data = {
            "company_name": "Acme",
            "ceo_name": "Alice",
            "ceo_email": None,
            "company_description": "",
            "news_articles": [],
        }
        # 2 out of 12 fields populated = 2/12 = 0.166...
        rate = compute_fill_rate(partial_data)
        assert 0.15 < rate < 0.20


class TestFormatErrorDetection:
    def test_detects_placeholder_strings(self):
        data = {
            "ceo_name": "not available",
            "industry": "N/A",
            "company_description": "unknown",
        }
        errors = compute_format_errors(data)
        assert len(errors) == 3

    def test_detects_invalid_email_format(self):
        data = {"ceo_email": "not-an-email"}
        errors = compute_format_errors(data)
        assert any("email" in e.lower() for e in errors)

    def test_clean_data_has_zero_format_errors(self):
        data = {
            "company_name": "Acme Inc",
            "ceo_name": "Jane Doe",
            "ceo_email": "jane@acme.com",
            "company_website": "https://acme.com",
        }
        assert len(compute_format_errors(data)) == 0


class TestGuardrailAndHallucinationRules:
    def test_catches_hallucination_without_sources(self):
        enriched = {
            "company_name": "Ghost Co",
            "fallback_confidence_score": 0.85,
            "fallback_sources_used": [],
        }
        issues = evaluate_single_lead(
            enriched,
            lead_status="completed",
            expected_case={"id": "test_hallucination", "expected": {}},
        )
        assert any("Hallucination" in issue for issue in issues)

    def test_accepts_high_confidence_with_sources(self):
        enriched = {
            "company_name": "Real Co",
            "fallback_confidence_score": 0.85,
            "fallback_sources_used": ["sec_filings", "bloomberg"],
        }
        issues = evaluate_single_lead(
            enriched,
            lead_status="completed",
            expected_case={"id": "test_legit", "expected": {}},
        )
        assert not any("Hallucination" in issue for issue in issues)


class TestGoldenDatasetIntegrity:
    def test_golden_dataset_has_twenty_cases(self, golden_dataset):
        assert len(golden_dataset) == 20

    def test_golden_dataset_ids_are_unique(self, golden_dataset):
        ids = [case["id"] for case in golden_dataset]
        assert len(ids) == len(set(ids))

    def test_batch_evaluation_passes_quality_gate(self, golden_dataset):
        # Build simulated runs from golden_dataset expectations
        runs = []
        for case in golden_dataset:
            # Construct simulated enriched output matching expected
            mock_api = case.get("mock_apis", {})
            mock_cb = mock_api.get("clearbit", {})
            mock_fb = case.get("mock_llm_fallback") or {}

            enriched = {
                "company_name": case["input"]["company_name"],
                "ceo_name": mock_fb.get("ceo_name") or case.get("expected", {}).get("ceo_name"),
                "ceo_email": mock_fb.get("ceo_email") or case.get("expected", {}).get("ceo_email"),
                "company_website": mock_fb.get("company_website") or case.get("expected", {}).get("company_website"),
                "founding_year": mock_cb.get("foundedYear") or mock_fb.get("founding_year"),
                "industry": mock_cb.get("category", {}).get("industry") or mock_fb.get("industry"),
                "fallback_confidence_score": mock_fb.get("confidence_score"),
                "fallback_sources_used": mock_fb.get("sources_used", []),
            }

            status = case.get("expected", {}).get("status", "completed")
            runs.append((enriched, status, case))

        report = evaluate_batch(runs)
        assert report.guardrail_accuracy == 1.0
        assert report.hallucination_violations == 0
        assert report.format_error_rate <= 0.05
