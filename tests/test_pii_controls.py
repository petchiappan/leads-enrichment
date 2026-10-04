"""
Unit tests for PII Controls and redaction in LLM prompts.
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from app.pipeline.fallback_agent import _build_user_prompt
from app.pipeline.guardrails import is_pii_redaction_enabled, redact_pii_from_dict
from tests.conftest import make_fake_session


class TestPiiDictRedaction:
    def test_pii_redaction_disabled_leaves_data_intact(self):
        session = make_fake_session({"guardrail.pii_redaction_enabled": "false"})
        data = {
            "ceo_email": "ceo@secretcompany.com",
            "notes": "Call 415-555-1234",
        }
        redacted = redact_pii_from_dict(data, session=session)
        assert redacted["ceo_email"] == "ceo@secretcompany.com"
        assert redacted["notes"] == "Call 415-555-1234"

    def test_pii_redaction_enabled_replaces_emails_and_phones(self):
        session = make_fake_session({"guardrail.pii_redaction_enabled": "true"})
        data = {
            "ceo_name": "John Doe",
            "ceo_email": "john.doe@enterprise.com",
            "phone": "+1 415-555-9876",
            "contacts": ["support@enterprise.com", "billing@enterprise.com"],
            "nested": {
                "direct_email": "direct@enterprise.com",
            },
        }
        redacted = redact_pii_from_dict(data, session=session)
        assert redacted["ceo_name"] == "John Doe"
        assert redacted["ceo_email"] == "[REDACTED_EMAIL]"
        assert "[REDACTED_PHONE]" in redacted["phone"]
        assert redacted["contacts"] == ["[REDACTED_EMAIL]", "[REDACTED_EMAIL]"]
        assert redacted["nested"]["direct_email"] == "[REDACTED_EMAIL]"

    def test_prompt_does_not_contain_raw_pii_when_sanitized(self):
        session = make_fake_session({"guardrail.pii_redaction_enabled": "true"})
        raw_existing = {
            "ceo_email": "private.ceo@corp.com",
            "contact_phone": "415-555-0000",
        }
        sanitized = redact_pii_from_dict(raw_existing, session=session)
        prompt = _build_user_prompt("Corp", ["industry"], sanitized)

        assert "private.ceo@corp.com" not in prompt
        assert "415-555-0000" not in prompt
        assert "[REDACTED_EMAIL]" in prompt
