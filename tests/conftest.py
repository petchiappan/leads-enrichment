"""
Shared pytest fixtures for the leads_enrichment_ai test suite.

Provides:
  - Lightweight in-memory admin_config mock via a fake Session
  - Reusable AgenticExtractionResult factory for test data
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── Fake DB session helpers ──────────────────────────────────────────────────


class FakeAdminConfigRow:
    """Minimal stub mimicking an AdminConfig ORM row."""

    def __init__(self, key: str, value: str) -> None:
        self.setting_key = key
        self.setting_value = value


def make_fake_session(config: dict[str, str] | None = None) -> MagicMock:
    """Return a MagicMock that behaves like a sync SQLAlchemy Session.

    When guardrails calls session.execute(select(AdminConfig).where(...)),
    the mock returns the value from `config` dict, or None if the key is absent.
    """
    config = config or {}
    session = MagicMock()

    def fake_execute(stmt):
        # Extract the key from the WHERE clause — simplified for testing
        # Guardrails always calls scalar_one_or_none() on the result
        result_mock = MagicMock()
        stmt_params = stmt.compile().params if hasattr(stmt, "compile") else {}
        matched_value = None
        for key, value in config.items():
            if key in stmt_params.values() or key in str(stmt):
                matched_value = FakeAdminConfigRow(key, value)
                break
        result_mock.scalar_one_or_none.return_value = matched_value
        return result_mock

    session.execute.side_effect = fake_execute
    return session


# ── AgenticExtractionResult factory ─────────────────────────────────────────


@pytest.fixture()
def valid_extraction_result():
    """A fully valid AgenticExtractionResult for use in tests."""
    from app.schemas.fallback import AgenticExtractionResult

    return AgenticExtractionResult(
        company_name="Acme Corp",
        ceo_name="Jane Doe",
        ceo_email="jane.doe@acmecorp.com",
        company_description="A leading widget manufacturer.",
        linkedin_url="https://linkedin.com/in/janedoe",
        linkedin_company_url="https://linkedin.com/company/acmecorp",
        employee_count=500,
        company_website="https://acmecorp.com",
        funding_raised="$10M Series A",
        industry="Manufacturing",
        founding_year=2005,
        news_articles=["Acme raises $10M", "Acme expands to APAC"],
        confidence_score=0.85,
        sources_used=["clearbit", "lusha"],
    )
