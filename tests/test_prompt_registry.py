"""
Unit tests for app/pipeline/prompt_registry.py and prompt versioning.

Tests:
  - Retrieval from hardcoded fallback when DB is empty or session is None
  - Retrieval from DB when an active row exists
  - Caching behaviour (TTL avoidance of extra queries)
  - Cache clearing
  - Fallback on database query error
  - Missing prompt name error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from app.pipeline import prompt_registry
from app.pipeline.prompt_registry import (
    ActivePrompt,
    clear_cache,
    get_active_prompt,
    get_active_prompt_id,
    get_active_prompt_version,
    load_active_prompt,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """Ensure prompt cache is cleared before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestPromptRegistryFallback:
    def test_load_fallback_system_prompt_without_session(self):
        content = load_active_prompt("fallback_system_prompt")
        assert "expert business intelligence analyst" in content
        assert "AgenticExtractionResult" not in content  # Prompt content itself

    def test_load_gate_prompt_without_session(self):
        content = load_active_prompt("intelligence_gate_prompt")
        assert "data quality assessor" in content

    def test_fallback_version_string(self):
        version = get_active_prompt_version("fallback_system_prompt")
        assert "fallback" in version

    def test_fallback_id_is_none(self):
        prompt_id = get_active_prompt_id("fallback_system_prompt")
        assert prompt_id is None

    def test_unknown_prompt_raises_key_error(self):
        with pytest.raises(KeyError):
            get_active_prompt("completely_unknown_prompt_name")


class TestPromptRegistryWithDB:
    def test_loads_from_db_when_row_present(self):
        fake_row = MagicMock()
        fake_row.id = 42
        fake_row.name = "fallback_system_prompt"
        fake_row.version = "v2.5.0"
        fake_row.content = "Custom dynamic prompt for v2.5.0"
        fake_row.environment = "production"
        fake_row.is_active = True

        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = fake_row

        active = get_active_prompt("fallback_system_prompt", session=session)

        assert active.id == 42
        assert active.version == "v2.5.0"
        assert active.content == "Custom dynamic prompt for v2.5.0"

    def test_in_process_cache_avoids_db_requery(self):
        fake_row = MagicMock()
        fake_row.id = 101
        fake_row.name = "intelligence_gate_prompt"
        fake_row.version = "v3.0.0"
        fake_row.content = "Dynamic gate content"
        fake_row.environment = "production"

        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = fake_row

        first = get_active_prompt("intelligence_gate_prompt", session=session)
        assert first.version == "v3.0.0"
        assert session.execute.call_count == 1

        # Second call should read from cache
        second = get_active_prompt("intelligence_gate_prompt", session=session)
        assert second.version == "v3.0.0"
        assert session.execute.call_count == 1  # Not called again

    def test_clear_cache_forces_db_requery(self):
        fake_row = MagicMock()
        fake_row.id = 102
        fake_row.name = "intelligence_gate_prompt"
        fake_row.version = "v3.0.0"
        fake_row.content = "Dynamic gate content"
        fake_row.environment = "production"

        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = fake_row

        get_active_prompt("intelligence_gate_prompt", session=session)
        assert session.execute.call_count == 1

        clear_cache()

        get_active_prompt("intelligence_gate_prompt", session=session)
        assert session.execute.call_count == 2

    def test_db_error_falls_back_to_hardcoded(self):
        session = MagicMock()
        session.execute.side_effect = RuntimeError("Database connection pool exhausted")

        # Must not raise an exception; should fall back to hardcoded
        active = get_active_prompt("fallback_system_prompt", session=session)
        assert active.id is None
        assert "fallback" in active.version
        assert "expert business intelligence analyst" in active.content
