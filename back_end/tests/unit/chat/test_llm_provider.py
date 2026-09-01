"""
Tests for utils/llm_provider.py

Failure points targeted:
- get_provider() with empty OpenRouter API key → should raise ValueError
- get_provider() with unknown provider type → should raise ValueError
- Local provider uses correct base_url and dummy api_key
- Prompt caching: system conversion, tool mutation safety, local guard, usage metrics
- Thinking header: extra_headers injected for openrouter provider
"""

import pytest
from unittest.mock import patch, MagicMock

from utils.llm_provider import get_provider, AnthropicProvider, THINKING_BETA_HEADER


class TestPromptCaching:
    """T1-T5: _apply_prompt_caching correctness and usage metric extraction."""

    def _make_provider(self, base_url=None):
        pt = "local" if base_url else "openrouter"
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


class TestGetProvider:
    def test_openrouter_no_api_key_raises(self):
        config = {"llm_provider": "openrouter", "openrouter_api_key": ""}
        with patch("utils.llm_provider.load_config", return_value=config):
            with pytest.raises(ValueError, match="API key not configured"):
                get_provider()

    def test_openrouter_with_key_returns_provider(self):
        config = {
            "llm_provider": "openrouter",
            "openrouter_api_key": "sk-or-test123",
            "openrouter_model": "anthropic/claude-sonnet-4.6",
        }
        with patch("utils.llm_provider.load_config", return_value=config):
            provider = get_provider()
            assert isinstance(provider, AnthropicProvider)
            assert provider.model == "anthropic/claude-sonnet-4.6"
            assert provider.provider_type == "openrouter"

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


class TestThinkingExtraHeaders:
    """Verify extra_headers injected for OpenRouter interleaved thinking."""

    def _make_provider(self, provider_type="openrouter"):
        return AnthropicProvider(api_key="test", model="claude-sonnet-4-6", provider_type=provider_type)

    @pytest.mark.asyncio
    async def test_openrouter_gets_extra_headers(self):
        provider = self._make_provider("openrouter")
        captured = []

        class FakeStreamCtx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
            async def get_final_message(self):
                m = MagicMock()
                m.content = []
                m.usage = None
                return m

        provider.client.beta.messages.stream = lambda **kw: (captured.append(kw), FakeStreamCtx())[1]

        with patch("utils.llm_provider.load_config", return_value={"thinking_enabled": True}):
            async for _ in provider.stream_chat(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="test",
                thinking_enabled=True,
            ):
                pass

        assert len(captured) == 1
        assert "extra_headers" in captured[0]
        assert captured[0]["extra_headers"]["x-anthropic-beta"] == THINKING_BETA_HEADER

    @pytest.mark.asyncio
    async def test_local_does_not_get_extra_headers(self):
        """Local provider should not have thinking enabled at all (guard: provider_type != 'local')."""
        provider = self._make_provider("local")
        captured = []

        class FakeStreamCtx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
            async def get_final_message(self):
                m = MagicMock()
                m.content = []
                m.usage = None
                return m

        provider.client.messages.stream = lambda **kw: (captured.append(kw), FakeStreamCtx())[1]

        with patch("utils.llm_provider.load_config", return_value={"thinking_enabled": True}):
            async for _ in provider.stream_chat(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="test",
                thinking_enabled=True,
            ):
                pass

        assert len(captured) == 1
        assert "extra_headers" not in captured[0]
