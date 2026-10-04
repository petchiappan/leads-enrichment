"""
Tests for Admin Dashboard SSR Views.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.lead import Lead
from app.models.prompt_version import PromptVersion


@pytest.fixture()
def client():
    return TestClient(app)


class TestAdminViews:
    def test_review_page_renders_with_pending_leads(self, client):
        req_id = uuid.uuid4()
        fake_lead = Lead(
            id=uuid.uuid4(),
            request_id=req_id,
            company_key="stripe.com",
            raw_input={"company_name": "Stripe"},
            status="needs_review",
            enriched_data={"confidence_score": 0.45, "sources_used": ["web_search"]},
            created_at=datetime.now(timezone.utc),
        )

        with patch("app.services.review_service.get_leads_needing_review", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [fake_lead]

            # Override get_db to avoid real postgres connection
            app.dependency_overrides[get_db] = lambda: AsyncMock()
            try:
                response = client.get("/admin/review")
                assert response.status_code == 200
                html = response.text
                assert "Human Review Queue" in html
                assert "Stripe" in html
                assert "45.0%" in html
                assert "Approve" in html
                assert "Reject" in html
                assert "Re-enrich" in html
            finally:
                app.dependency_overrides.pop(get_db, None)

    def test_prompts_page_renders_active_versions(self, client):
        fake_prompt = PromptVersion(
            id=1,
            name="fallback_system_prompt",
            version="v1.0.0",
            content="You are an expert lead researcher.",
            environment="production",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        with patch("app.services.prompt_service.get_all_prompts", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [fake_prompt]

            app.dependency_overrides[get_db] = lambda: AsyncMock()
            try:
                response = client.get("/admin/prompts")
                assert response.status_code == 200
                html = response.text
                assert "Prompt Management" in html
                assert "fallback_system_prompt" in html
                assert "v1.0.0" in html
                assert "ACTIVE" in html
            finally:
                app.dependency_overrides.pop(get_db, None)

    def test_lead_detail_renders_provenance_badges(self, client):
        req_id = uuid.uuid4()
        fake_lead = Lead(
            id=uuid.uuid4(),
            request_id=req_id,
            company_key="openai.com",
            raw_input={"company_name": "OpenAI"},
            status="completed",
            enriched_data={
                "company_name": "OpenAI",
                "ceo_name": "Sam Altman",
                "ceo_email": "sam@openai.com",
                "_field_provenance": {
                    "company_name": "clearbit",
                    "ceo_name": "hunter",
                    "ceo_email": "lusha",
                },
            },
            created_at=datetime.now(timezone.utc),
            enriched_at=datetime.now(timezone.utc),
        )

        with patch("app.services.lead_service.get_lead_by_request_id", new_callable=AsyncMock) as mock_lead, \
             patch("app.services.pipeline_service.get_logs_for_request", new_callable=AsyncMock) as mock_logs, \
             patch("app.services.token_service.get_usage_by_request", new_callable=AsyncMock) as mock_tokens:

            mock_lead.return_value = fake_lead
            mock_logs.return_value = []
            mock_tokens.return_value = []

            app.dependency_overrides[get_db] = lambda: AsyncMock()
            try:
                response = client.get(f"/admin/leads/{req_id}")
                assert response.status_code == 200
                html = response.text
                assert "OpenAI" in html
                assert "openai.com" in html
                assert "Field-Level Provenance" in html
                assert "clearbit" in html
                assert "hunter" in html
                assert "lusha" in html
            finally:
                app.dependency_overrides.pop(get_db, None)
