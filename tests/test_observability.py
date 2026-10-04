"""
Unit tests for app/services/observability.py, context, and metrics.

Tests:
  - Context request_id propagation
  - PII redaction (email and phone)
  - RequestIdFilter log record enrichment
  - timed_llm_call duration measurement and metric recording
  - Prometheus /metrics endpoint via FastAPI TestClient
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app import metrics
from app.main import app
from app.pipeline import context
from app.services import observability
from app.services.observability import (
    RequestIdFilter,
    configure_logging,
    redact_pii,
    timed_llm_call,
)


class TestPipelineContext:
    def test_set_and_get_request_id(self):
        context.set_request_id("test-req-12345")
        assert context.get_request_id() == "test-req-12345"

    def test_empty_request_id_defaults_to_empty(self):
        context.set_request_id("")
        assert context.get_request_id() == ""


class TestPiiRedaction:
    def test_redacts_single_email(self):
        text = "Contact the CEO at john.doe@example.com for inquiries."
        redacted = redact_pii(text)
        assert "john.doe@example.com" not in redacted
        assert "[REDACTED_EMAIL]" in redacted

    def test_redacts_multiple_emails(self):
        text = "Emails: alice@co.org and bob@tech.io"
        redacted = redact_pii(text)
        assert "alice@co.org" not in redacted
        assert "bob@tech.io" not in redacted
        assert redacted.count("[REDACTED_EMAIL]") == 2

    def test_redacts_phone_numbers(self):
        text = "Call us at +1 415-555-1234 or 555-123-4567"
        redacted = redact_pii(text)
        assert "555-1234" not in redacted
        assert "[REDACTED_PHONE]" in redacted

    def test_preserves_clean_text(self):
        text = "Acme Corp is an enterprise SaaS platform founded in 2021."
        assert redact_pii(text) == text

    def test_handles_non_string_input(self):
        assert redact_pii(None) is None


class TestRequestIdFilter:
    def test_filter_injects_current_request_id(self):
        context.set_request_id("req-uuid-999")
        log_filter = RequestIdFilter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="Test log message",
            args=(),
            exc_info=None,
        )
        assert log_filter.filter(record) is True
        assert record.request_id == "req-uuid-999"

    def test_filter_defaults_to_dash_when_empty(self):
        context.set_request_id("")
        log_filter = RequestIdFilter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="Test log message",
            args=(),
            exc_info=None,
        )
        log_filter.filter(record)
        assert record.request_id == "-"


class TestTimedLlmCall:
    def test_timed_call_returns_response_and_duration(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        response, duration_s = timed_llm_call(
            client=mock_client,
            step_name="test_step",
            model="gpt-4o",
            messages=[{"role": "user", "content": "hello"}],
        )

        assert response == mock_response
        assert isinstance(duration_s, float)
        assert duration_s >= 0.0
        assert mock_client.chat.completions.create.call_count == 1

    def test_timed_call_propagates_exceptions(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("OpenAI 500 internal error")

        with pytest.raises(RuntimeError):
            timed_llm_call(
                client=mock_client,
                step_name="test_step",
                model="gpt-4o",
                messages=[{"role": "user", "content": "fail"}],
            )


class TestMetricsEndpoint:
    @pytest.fixture()
    def client(self):
        return TestClient(app)

    def test_metrics_endpoint_returns_prometheus_data(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        assert "enrichment_pipeline_total" in content
        assert "llm_call_duration_seconds" in content
        assert "llm_tokens_total" in content
        assert "guardrail_violations_total" in content
