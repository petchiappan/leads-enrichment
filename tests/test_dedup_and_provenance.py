"""
Unit tests for Lead Deduplication and Field-Level Source Provenance.
"""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock
import pytest

from app.models.lead import Lead
from app.pipeline import steps
from app.schemas.fallback import AgenticExtractionResult
from app.services.lead_service import compute_company_key


class TestDeduplicationKeys:
    def test_domain_canonicalization(self):
        assert compute_company_key("Stripe Inc", "stripe.com") == "domain:stripe.com"
        assert compute_company_key("Stripe", "https://www.stripe.com/about") == "domain:stripe.com"
        assert compute_company_key("Stripe", "http://stripe.com/") == "domain:stripe.com"

    def test_name_canonicalization_without_domain(self):
        assert compute_company_key("Acme, Inc.!!") == "name:acme inc"
        assert compute_company_key("   OpenAI   ") == "name:openai"


class TestFieldProvenance:
    def test_merge_results_assigns_field_provenance(self):
        api_data = {
            "company_name": "Acme Corp",
            "company_website": "https://acme.com",
            "_field_provenance": {
                "company_name": "clearbit",
                "company_website": "clearbit",
            },
            "_api_sources_used": ["clearbit"],
        }

        fallback_data = AgenticExtractionResult(
            company_name="Acme Corp",
            ceo_name="Jane Doe",
            ceo_email="jane@acme.com",
            confidence_score=0.9,
            sources_used=["press_release"],
        )

        merged = steps._merge_results(api_data, fallback_data)

        provenance = merged.get("_field_provenance")
        assert provenance is not None
        assert provenance["company_name"] == "clearbit"
        assert provenance["company_website"] == "clearbit"
        assert provenance["ceo_name"] == "fallback"
        assert provenance["ceo_email"] == "fallback"
        assert provenance["fallback_confidence_score"] == "fallback"


class TestEnrichedAtTimestamp:
    def test_save_final_lineage_sets_enriched_at_on_completion(self):
        mock_session = MagicMock()
        request_id = uuid.uuid4()
        fake_lead = Lead(
            id=uuid.uuid4(),
            request_id=request_id,
            raw_input={"company_name": "Test"},
            status="processing",
            enriched_at=None,
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.services.lead_service.get_lead_by_request_id_sync", lambda s, rid: fake_lead)
            mp.setattr("app.services.embedding_service.store_embedding_sync", lambda **kwargs: None)

            api_data = {"company_name": "Test"}
            steps.save_final_lineage(mock_session, request_id, api_data, None)

            assert fake_lead.status == "completed"
            assert fake_lead.enriched_at is not None
            assert isinstance(fake_lead.enriched_at, datetime.datetime)
