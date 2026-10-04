"""
Unit tests for app/schemas/fallback.py field validators.

Tests that malformed LLM output is coerced to None rather than stored as-is.
All tests are pure Pydantic validation — no DB, no OpenAI, no HTTP calls.
"""

from __future__ import annotations

import datetime

import pytest

from app.schemas.fallback import AgenticExtractionResult

# Minimal valid base kwargs — every test overrides one field at a time
BASE = dict(
    company_name="TestCo",
    confidence_score=0.8,
    sources_used=["test"],
)


# ── ceo_email ────────────────────────────────────────────────────────────────


class TestCeoEmailValidator:
    def test_valid_email_kept(self):
        r = AgenticExtractionResult(**BASE, ceo_email="alice@example.com")
        assert r.ceo_email == "alice@example.com"

    def test_none_stays_none(self):
        r = AgenticExtractionResult(**BASE, ceo_email=None)
        assert r.ceo_email is None

    def test_placeholder_string_coerced(self):
        r = AgenticExtractionResult(**BASE, ceo_email="not available")
        assert r.ceo_email is None

    def test_bare_name_coerced(self):
        r = AgenticExtractionResult(**BASE, ceo_email="Alice Smith")
        assert r.ceo_email is None

    def test_bare_domain_coerced(self):
        r = AgenticExtractionResult(**BASE, ceo_email="example.com")
        assert r.ceo_email is None

    def test_email_with_whitespace_stripped(self):
        r = AgenticExtractionResult(**BASE, ceo_email="  alice@example.com  ")
        assert r.ceo_email == "alice@example.com"

    def test_unknown_string_coerced(self):
        r = AgenticExtractionResult(**BASE, ceo_email="unknown")
        assert r.ceo_email is None

    def test_empty_string_coerced(self):
        r = AgenticExtractionResult(**BASE, ceo_email="")
        assert r.ceo_email is None


# ── company_website / linkedin_url / linkedin_company_url ────────────────────


class TestUrlValidators:
    @pytest.mark.parametrize("field", ["company_website", "linkedin_url", "linkedin_company_url"])
    def test_valid_https_url_kept(self, field):
        r = AgenticExtractionResult(**BASE, **{field: "https://example.com"})
        assert getattr(r, field) == "https://example.com"

    @pytest.mark.parametrize("field", ["company_website", "linkedin_url", "linkedin_company_url"])
    def test_valid_http_url_kept(self, field):
        r = AgenticExtractionResult(**BASE, **{field: "http://example.com/path"})
        assert getattr(r, field) == "http://example.com/path"

    @pytest.mark.parametrize("field", ["company_website", "linkedin_url", "linkedin_company_url"])
    def test_bare_domain_coerced(self, field):
        r = AgenticExtractionResult(**BASE, **{field: "example.com"})
        assert getattr(r, field) is None

    @pytest.mark.parametrize("field", ["company_website", "linkedin_url", "linkedin_company_url"])
    def test_placeholder_coerced(self, field):
        r = AgenticExtractionResult(**BASE, **{field: "N/A"})
        assert getattr(r, field) is None

    @pytest.mark.parametrize("field", ["company_website", "linkedin_url", "linkedin_company_url"])
    def test_none_stays_none(self, field):
        r = AgenticExtractionResult(**BASE, **{field: None})
        assert getattr(r, field) is None

    @pytest.mark.parametrize("field", ["company_website", "linkedin_url", "linkedin_company_url"])
    def test_empty_string_coerced(self, field):
        r = AgenticExtractionResult(**BASE, **{field: ""})
        assert getattr(r, field) is None


# ── founding_year ────────────────────────────────────────────────────────────


class TestFoundingYearValidator:
    def test_valid_year_kept(self):
        r = AgenticExtractionResult(**BASE, founding_year=2010)
        assert r.founding_year == 2010

    def test_min_boundary_kept(self):
        r = AgenticExtractionResult(**BASE, founding_year=1800)
        assert r.founding_year == 1800

    def test_current_year_kept(self):
        current = datetime.date.today().year
        r = AgenticExtractionResult(**BASE, founding_year=current)
        assert r.founding_year == current

    def test_future_year_coerced(self):
        future = datetime.date.today().year + 1
        r = AgenticExtractionResult(**BASE, founding_year=future)
        assert r.founding_year is None

    def test_year_3000_coerced(self):
        r = AgenticExtractionResult(**BASE, founding_year=3000)
        assert r.founding_year is None

    def test_year_1799_coerced(self):
        r = AgenticExtractionResult(**BASE, founding_year=1799)
        assert r.founding_year is None

    def test_string_year_converted(self):
        r = AgenticExtractionResult(**BASE, founding_year="2015")
        assert r.founding_year == 2015

    def test_non_numeric_string_coerced(self):
        r = AgenticExtractionResult(**BASE, founding_year="unknown")
        assert r.founding_year is None

    def test_none_stays_none(self):
        r = AgenticExtractionResult(**BASE, founding_year=None)
        assert r.founding_year is None


# ── employee_count ───────────────────────────────────────────────────────────


class TestEmployeeCountValidator:
    def test_valid_count_kept(self):
        r = AgenticExtractionResult(**BASE, employee_count=500)
        assert r.employee_count == 500

    def test_zero_coerced(self):
        r = AgenticExtractionResult(**BASE, employee_count=0)
        assert r.employee_count is None

    def test_negative_coerced(self):
        r = AgenticExtractionResult(**BASE, employee_count=-10)
        assert r.employee_count is None

    def test_none_stays_none(self):
        r = AgenticExtractionResult(**BASE, employee_count=None)
        assert r.employee_count is None

    def test_string_count_converted(self):
        r = AgenticExtractionResult(**BASE, employee_count="200")
        assert r.employee_count == 200

    def test_non_numeric_string_coerced(self):
        r = AgenticExtractionResult(**BASE, employee_count="about 200")
        assert r.employee_count is None


# ── Empty string coercion (ceo_name, industry, etc.) ────────────────────────


class TestEmptyStringCoercion:
    @pytest.mark.parametrize("field", ["ceo_name", "company_description", "industry", "funding_raised"])
    def test_empty_string_coerced_to_none(self, field):
        r = AgenticExtractionResult(**BASE, **{field: ""})
        assert getattr(r, field) is None

    @pytest.mark.parametrize("field", ["ceo_name", "company_description", "industry", "funding_raised"])
    def test_whitespace_only_coerced_to_none(self, field):
        r = AgenticExtractionResult(**BASE, **{field: "   "})
        assert getattr(r, field) is None

    @pytest.mark.parametrize("field", ["ceo_name", "company_description", "industry", "funding_raised"])
    def test_valid_string_kept(self, field):
        r = AgenticExtractionResult(**BASE, **{field: "Some value"})
        assert getattr(r, field) == "Some value"


# ── confidence_score boundary ────────────────────────────────────────────────


from pydantic import ValidationError


class TestConfidenceScore:
    def test_zero_is_valid(self):
        r = AgenticExtractionResult(**dict(BASE, confidence_score=0.0))
        assert r.confidence_score == 0.0

    def test_one_is_valid(self):
        r = AgenticExtractionResult(**dict(BASE, confidence_score=1.0))
        assert r.confidence_score == 1.0

    def test_above_one_raises(self):
        with pytest.raises(ValidationError):
            AgenticExtractionResult(**dict(BASE, confidence_score=1.1))

    def test_below_zero_raises(self):
        with pytest.raises(ValidationError):
            AgenticExtractionResult(**dict(BASE, confidence_score=-0.1))

