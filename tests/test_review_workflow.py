"""
Unit tests for the Human Review workflow and review API endpoints.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.lead import Lead
from app.services import review_service


class TestReviewServiceLogic:
    @pytest.mark.asyncio
    async def test_approve_lead_sets_completed(self):
        req_id = uuid.uuid4()
        fake_lead = Lead(
            id=uuid.uuid4(),
            request_id=req_id,
            raw_input={"company_name": "Test"},
            status="needs_review",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_lead
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        audit = await review_service.review_lead(
            session=mock_session,
            request_id=req_id,
            action="approved",
            reviewer="reviewer@example.com",
            notes="Looks verified",
        )

        assert fake_lead.status == "completed"
        assert audit.action == "approved"
        assert audit.reviewer == "reviewer@example.com"
        assert audit.notes == "Looks verified"

    @pytest.mark.asyncio
    async def test_reject_lead_sets_failed(self):
        req_id = uuid.uuid4()
        fake_lead = Lead(
            id=uuid.uuid4(),
            request_id=req_id,
            raw_input={"company_name": "Test"},
            status="needs_review",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_lead
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        audit = await review_service.review_lead(
            session=mock_session,
            request_id=req_id,
            action="rejected",
            reviewer="reviewer@example.com",
            notes="Company does not exist",
        )

        assert fake_lead.status == "failed"
        assert audit.action == "rejected"

    @pytest.mark.asyncio
    @patch("app.services.review_service.run_enrichment_pipeline")
    async def test_re_enrich_lead_sets_processing_and_dispatches_task(self, mock_celery_task):
        req_id = uuid.uuid4()
        fake_lead = Lead(
            id=uuid.uuid4(),
            request_id=req_id,
            raw_input={"company_name": "Acme Inc"},
            status="needs_review",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_lead
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()



        audit = await review_service.review_lead(
            session=mock_session,
            request_id=req_id,
            action="re_enriched",
            reviewer="admin",
        )

        assert fake_lead.status == "processing"
        assert audit.action == "re_enriched"
        mock_celery_task.delay.assert_called_once_with(
            request_id_str=str(req_id),
            raw_input=fake_lead.raw_input,
        )


class TestReviewApiEndpoints:
    @pytest.fixture()
    def client(self):
        return TestClient(app)

    @patch("app.services.review_service.get_leads_needing_review")
    def test_list_needs_review_endpoint(self, mock_get_leads, client):
        req_id = uuid.uuid4()
        fake_lead = Lead(
            id=uuid.uuid4(),
            request_id=req_id,
            raw_input={"company_name": "NeedsReview Corp"},
            status="needs_review",
            enriched_data={"fallback_confidence_score": 0.2},
        )
        mock_get_leads.return_value = [fake_lead]

        response = client.get("/api/leads/needs-review")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["company_name"] == "NeedsReview Corp"
        assert data["items"][0]["status"] == "needs_review"
