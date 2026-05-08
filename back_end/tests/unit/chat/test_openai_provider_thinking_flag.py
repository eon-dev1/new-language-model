"""
Tests for global thinking_enabled flag enforcement in OpenAIProvider.

Mirrors test_thinking_flag.py (which guards AnthropicProvider).
Uses _build_payload as a pure function — no httpx mocking needed.
"""

from unittest.mock import patch

from utils.openai_provider import OpenAIProvider


def _make_provider():
    return OpenAIProvider(api_key="test", model="qwen/qwen3.5-397b-a17b")


def test_global_flag_false_forces_reasoning_disabled():
    """Request asks for thinking, global flag off → payload must suppress reasoning."""
    p = _make_provider()
    with patch("utils.openai_provider.load_config", return_value={"thinking_enabled": False}):
        payload = p._build_payload(
            messages=[{"role": "user", "content": "hi"}],
            system_prompt="test",
            tools=None,
            max_tokens=4096,
            thinking_enabled=True,  # request wants thinking
        )
    assert payload["reasoning"] == {"enabled": False}


def test_global_flag_true_allows_reasoning_effort_high():
    """Both flags on → payload requests reasoning."""
    p = _make_provider()
    with patch("utils.openai_provider.load_config", return_value={"thinking_enabled": True}):
        payload = p._build_payload(
            messages=[{"role": "user", "content": "hi"}],
            system_prompt="test",
            tools=None,
            max_tokens=4096,
            thinking_enabled=True,
        )
    assert payload["reasoning"] == {"effort": "high"}
