"""
Tests for the global thinking_enabled feature flag — backend enforcement.

Failure points targeted:
- T1: Global flag False blocks beta endpoint even when request asks for thinking
- T2: Global flag True allows beta endpoint when request asks for thinking
"""

import pytest
from unittest.mock import patch, MagicMock

from utils.llm_provider import AnthropicProvider


class FakeStreamCtx:
    """Minimal async context manager that yields nothing — used to probe endpoint selection."""

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


class TestGlobalThinkingGate:
    """Verify the global config flag gates beta endpoint selection in stream_chat."""

    def _make_provider(self):
        return AnthropicProvider(api_key="test", model="claude-sonnet-4-6", provider_type="anthropic")

    @pytest.mark.asyncio
    async def test_global_flag_false_blocks_beta_even_when_requested(self):
        """
        T1: Request asks for thinking, global config says no → regular endpoint used.

        Regression: If the load_config() AND-chain is missing or inverted,
        the beta endpoint is called despite the admin disabling thinking globally.
        """
        provider = self._make_provider()
        beta_called = []
        regular_called = []

        provider.client.beta.messages.stream = lambda **kw: (beta_called.append(kw), FakeStreamCtx())[1]
        provider.client.messages.stream = lambda **kw: (regular_called.append(kw), FakeStreamCtx())[1]

        with patch("utils.llm_provider.load_config", return_value={"thinking_enabled": False}):
            async for _ in provider.stream_chat(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="test",
                thinking_enabled=True,  # request wants thinking
            ):
                pass

        assert len(beta_called) == 0, "Beta endpoint called despite global flag being False"
        assert len(regular_called) == 1, "Regular endpoint not called"

    @pytest.mark.asyncio
    async def test_global_flag_true_allows_beta_when_requested(self):
        """
        T2: Global flag on + request wants thinking + model supports it → beta endpoint used.

        Regression: If the global flag check is incorrectly inverted or short-circuits
        too eagerly, thinking never activates even when the flag is on.
        """
        provider = self._make_provider()
        beta_called = []

        provider.client.beta.messages.stream = lambda **kw: (beta_called.append(kw), FakeStreamCtx())[1]
        # Regular stream should not be called in this path; leave it unmocked to fail loudly if hit

        with patch("utils.llm_provider.load_config", return_value={"thinking_enabled": True}):
            async for _ in provider.stream_chat(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="test",
                thinking_enabled=True,
            ):
                pass

        assert len(beta_called) == 1, "Beta endpoint not called when it should be"
        assert "thinking" in beta_called[0], "thinking param missing from beta call"
        assert "betas" in beta_called[0], "betas header missing from beta call"
