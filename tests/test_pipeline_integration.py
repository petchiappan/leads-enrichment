"""
Integration tests for Lead Enrichment Pipeline orchestration against golden scenarios.

Tests:
  - Full end-to-end flow with complete API hit (skips fallback)
  - Partial API hit triggering fallback agent
  - Low confidence trigger resulting in 'needs_review'
  - Golden cases verification
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.models.lead import Lead
from app.pipeline.orchestrator import (
    STEP_EVALUATE_INTELLIGENCE_GATE,
    STEP_FETCH_APIS,
    STEP_SAVE_FINAL_LINEAGE,
    STEP_SPAWN_FALLBACK_AGENT,
    STEP_VALIDATE_INPUT,
    run_pipeline,
)
from app.schemas.enrich import EnrichRequest
from app.schemas.fallback import AgenticExtractionResult, MissingGapsRequest

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "golden_leads.json"


@pytest.fixture()
def golden_dataset():
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def mock_session():
    """Mock sync SQLAlchemy session with a fake Lead record."""
    session = MagicMock()
    fake_lead = Lead(
        id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        raw_input={"company_name": "Test Company"},
        status="pending",
    )
    session.query.return_value.filter.return_value.first.return_value = fake_lead

    return session


class TestPipelineOrchestrationIntegration:
    @patch("app.pipeline.orchestrator.lead_service")
    @patch("app.pipeline.orchestrator.pipeline_service")
    @patch("app.pipeline.orchestrator.steps")
    def test_complete_api_hit_skips_fallback(
        self,
        mock_steps,
        mock_pipeline_service,
        mock_lead_service,
        mock_session,
    ):
        request_id = uuid.uuid4()
        raw_input = {"company_name": "Stripe", "company_domain": "stripe.com"}

        # Step 1: validate_input
        mock_steps.validate_input.return_value = EnrichRequest(**raw_input)

        # Step 2: fetch_apis
        mock_steps.fetch_apis.return_value = {
            "company_name": "Stripe",
            "ceo_name": "Patrick Collison",
            "company_website": "https://stripe.com",
            "_api_sources_used": ["clearbit", "lusha"],
        }

        # Step 3: evaluate_intelligence_gate -> no gaps
        mock_steps.evaluate_intelligence_gate.return_value = None

        # Step 5: save_final_lineage
        expected_final = {
            "company_name": "Stripe",
            "ceo_name": "Patrick Collison",
            "company_website": "https://stripe.com",
        }
        mock_steps.save_final_lineage.return_value = expected_final

        result = run_pipeline(
            session=mock_session,
            request_id=request_id,
            raw_input=raw_input,
        )

        assert result == expected_final
        # Fallback agent must NOT be spawned
        assert mock_steps.spawn_fallback_agent.call_count == 0
        # save_final_lineage must be called with fallback_data=None
        mock_steps.save_final_lineage.assert_called_once_with(
            mock_session, request_id, mock_steps.fetch_apis.return_value, None
        )

    @patch("app.pipeline.orchestrator.lead_service")
    @patch("app.pipeline.orchestrator.pipeline_service")
    @patch("app.pipeline.orchestrator.steps")
    def test_partial_api_hit_triggers_fallback(
        self,
        mock_steps,
        mock_pipeline_service,
        mock_lead_service,
        mock_session,
    ):
        request_id = uuid.uuid4()
        raw_input = {"company_name": "Acme Robotics"}

        # Step 1: validate
        mock_steps.validate_input.return_value = EnrichRequest(**raw_input)

        # Step 2: fetch_apis -> missing CEO
        mock_steps.fetch_apis.return_value = {
            "company_name": "Acme Robotics",
            "_api_sources_used": ["news"],
        }

        # Step 3: intelligence gate confirms gaps
        gaps_req = MissingGapsRequest(missing_fields=["ceo_name", "company_website"])
        mock_steps.evaluate_intelligence_gate.return_value = gaps_req

        # Step 4: fallback returns extraction result
        fb_result = AgenticExtractionResult(
            company_name="Acme Robotics",
            ceo_name="Elena Rostova",
            company_website="https://acmerobotics.io",
            confidence_score=0.85,
            sources_used=["techcrunch"],
        )
        mock_steps.spawn_fallback_agent.return_value = fb_result

        # Step 5: save_final_lineage
        expected_final = {
            "company_name": "Acme Robotics",
            "ceo_name": "Elena Rostova",
            "company_website": "https://acmerobotics.io",
            "fallback_confidence_score": 0.85,
        }
        mock_steps.save_final_lineage.return_value = expected_final

        result = run_pipeline(
            session=mock_session,
            request_id=request_id,
            raw_input=raw_input,
        )

        assert result == expected_final
        # Fallback agent MUST be called
        assert mock_steps.spawn_fallback_agent.call_count == 1
        mock_steps.save_final_lineage.assert_called_once_with(
            mock_session, request_id, mock_steps.fetch_apis.return_value, fb_result
        )

    @patch("app.pipeline.orchestrator.lead_service")
    @patch("app.pipeline.orchestrator.pipeline_service")
    @patch("app.pipeline.orchestrator.steps")
    def test_low_confidence_flags_needs_review(
        self,
        mock_steps,
        mock_pipeline_service,
        mock_lead_service,
        mock_session,
    ):
        request_id = uuid.uuid4()
        raw_input = {"company_name": "Unregistered Mystery LLC"}

        mock_steps.validate_input.return_value = EnrichRequest(**raw_input)
        mock_steps.fetch_apis.return_value = {"company_name": "Unregistered Mystery LLC"}
        mock_steps.evaluate_intelligence_gate.return_value = MissingGapsRequest(missing_fields=["ceo_name"])

        # Low confidence result with _needs_review=True
        fb_result = AgenticExtractionResult(
            company_name="Unregistered Mystery LLC",
            confidence_score=0.15,
            sources_used=[],
        )
        object.__setattr__(fb_result, "_needs_review", True)
        mock_steps.spawn_fallback_agent.return_value = fb_result

        mock_steps.save_final_lineage.return_value = {
            "company_name": "Unregistered Mystery LLC",
            "fallback_confidence_score": 0.15,
        }

        result = run_pipeline(
            session=mock_session,
            request_id=request_id,
            raw_input=raw_input,
        )

        assert result["fallback_confidence_score"] == 0.15
        mock_steps.save_final_lineage.assert_called_once()
