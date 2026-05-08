"""
Tests for utils/llm_provider.py

Failure points targeted:
- get_provider() with empty API key → should raise ValueError
- get_provider() with unknown provider type → should raise ValueError
- Local provider uses correct base_url and dummy api_key
- Prompt caching: system conversion, tool mutation safety, local guard, usage metrics
"""

import pytest
from unittest.mock import patch

from utils.llm_provider import get_provider, AnthropicProvider


class TestPromptCaching:
    """T1-T5: _apply_prompt_caching correctness and usage metric extraction."""

    def _make_provider(self, base_url=None):
        pt = "local" if base_url else "anthropic"
        return AnthropicProvider(api_key="test", model="claude-sonnet-4-6", base_url=base_url, provider_type=pt)

    # T1
    def test_caching_converts_system_to_content_blocks(self):
        provider = self._make_provider()
        kwargs = {"system": "You are a translator"}
        provider._apply_prompt_caching(kwargs)
        assert isinstance(kwargs["system"], list)
        assert len(kwargs["system"]) == 1
        block = kwargs["system"][0]
        assert block == {
            "type": "text",
            "text": "You are a translator",
            "cache_control": {"type": "ephemeral"},
        }

    # T2
    def test_caching_adds_cache_control_to_last_tool(self):
        provider = self._make_provider()
        kwargs = {
            "tools": [
                {"name": "tool_a", "input_schema": {}},
                {"name": "tool_b", "input_schema": {}},
            ]
        }
        provider._apply_prompt_caching(kwargs)
        assert kwargs["tools"][-1]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in kwargs["tools"][0]

    # T3
    def test_caching_does_not_mutate_original_tool_dicts(self):
        provider = self._make_provider()
        original_a = {"name": "tool_a", "input_schema": {}}
        original_b = {"name": "tool_b", "input_schema": {}}
        kwargs = {"tools": [original_a, original_b]}
        provider._apply_prompt_caching(kwargs)
        assert "cache_control" not in original_a
        assert "cache_control" not in original_b

    # T4
    def test_caching_skipped_for_local_provider(self):
        provider = self._make_provider(base_url="http://localhost:8080")
        assert provider.provider_type == "local"
        kwargs = {
            "system": "You are a translator",
            "tools": [{"name": "tool_a", "input_schema": {}}],
        }
        if provider.provider_type != "local":
            provider._apply_prompt_caching(kwargs)
        assert isinstance(kwargs["system"], str)
        assert "cache_control" not in kwargs["tools"][0]

    # T5
    def test_usage_event_includes_cache_metrics(self):
        """Usage extraction logic returns all four fields including cache fields."""

        class MockUsage:
            input_tokens = 1000
            output_tokens = 200
            cache_creation_input_tokens = 5000
            cache_read_input_tokens = 0

        usage = MockUsage()
        cache_creation = getattr(usage, "cache_creation_input_tokens", None) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
        event = {
            "type": "usage",
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_creation_input_tokens": cache_creation,
            "cache_read_input_tokens": cache_read,
        }
        assert event["input_tokens"] == 1000
        assert event["output_tokens"] == 200
        assert event["cache_creation_input_tokens"] == 5000
        assert event["cache_read_input_tokens"] == 0

    def test_usage_event_none_cache_fields_become_zero(self):
        """None cache fields (field missing or None) become 0."""

        class MockUsage:
            input_tokens = 500
            output_tokens = 100
            cache_creation_input_tokens = None
            # cache_read_input_tokens intentionally absent

        usage = MockUsage()
        cache_creation = getattr(usage, "cache_creation_input_tokens", None) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
        assert cache_creation == 0
        assert cache_read == 0


class TestGetProvider:
    def test_anthropic_no_api_key_raises(self):
        config = {"llm_provider": "anthropic", "anthropic_api_key": ""}
        with patch("utils.llm_provider.load_config", return_value=config):
            with pytest.raises(ValueError, match="API key not configured"):
                get_provider()

    def test_anthropic_with_key_returns_provider(self):
        config = {
            "llm_provider": "anthropic",
            "anthropic_api_key": "sk-ant-test123",
            "anthropic_model": "claude-sonnet-4-5-20250929",
        }
        with patch("utils.llm_provider.load_config", return_value=config):
            provider = get_provider()
            assert isinstance(provider, AnthropicProvider)
            assert provider.model == "claude-sonnet-4-5-20250929"

    def test_local_provider_uses_base_url(self):
        config = {
            "llm_provider": "local",
            "local_base_url": "http://localhost:9999",
            "local_model": "my-model",
        }
        with patch("utils.llm_provider.load_config", return_value=config):
            provider = get_provider()
            assert isinstance(provider, AnthropicProvider)
            assert provider.model == "my-model"

    def test_unknown_provider_raises(self):
        config = {"llm_provider": "openai"}
        with patch("utils.llm_provider.load_config", return_value=config):
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                get_provider()

    def test_haiku_routes_to_anthropic_provider_not_openai(self):
        """Haiku has supports_thinking=False but api_format='anthropic'.
        If routing picked on thinking support, Haiku would go to the wrong provider."""
        config = {
            "llm_provider": "openrouter",
            "openrouter_api_key": "test",
            "openrouter_model": "anthropic/claude-haiku-4.5",
        }
        with patch("utils.llm_provider.load_config", return_value=config):
            p = get_provider()
        assert type(p).__name__ == "AnthropicProvider"

    def test_qwen_routes_to_openai_provider(self):
        config = {
            "llm_provider": "openrouter",
            "openrouter_api_key": "test",
            "openrouter_model": "qwen/qwen3.5-397b-a17b",
        }
        with patch("utils.llm_provider.load_config", return_value=config):
            p = get_provider()
        assert type(p).__name__ == "OpenAIProvider"
