import pytest

from shared.model_registry import get_context_window, supports_thinking, ALL_MODELS


class TestContextWindows:
    def test_anthropic_sonnet_is_1m(self):
        # Regression against stale 200K value
        assert get_context_window("claude-sonnet-4-6") == 1_000_000

    def test_anthropic_opus_is_1m(self):
        assert get_context_window("claude-opus-4-6") == 1_000_000

    def test_anthropic_haiku_is_200k(self):
        assert get_context_window("claude-haiku-4-5-20251001") == 200_000

    def test_openrouter_sonnet_is_1m(self):
        assert get_context_window("anthropic/claude-sonnet-4.6") == 1_000_000

    def test_openrouter_haiku_is_200k(self):
        assert get_context_window("anthropic/claude-haiku-4.5") == 200_000

    def test_qwen_context_window(self):
        assert get_context_window("qwen/qwen3.5-397b-a17b") == 262_144

    def test_unknown_model_returns_default(self):
        assert get_context_window("some-unknown-model") == 200_000


class TestSupportsThinking:
    def test_anthropic_sonnet_supports_thinking(self):
        assert supports_thinking("claude-sonnet-4-6") is True

    def test_anthropic_opus_supports_thinking(self):
        assert supports_thinking("claude-opus-4-6") is True

    def test_anthropic_haiku_does_not_support_thinking(self):
        assert supports_thinking("claude-haiku-4-5-20251001") is False

    def test_openrouter_sonnet_supports_thinking(self):
        assert supports_thinking("anthropic/claude-sonnet-4.6") is True

    def test_openrouter_haiku_does_not_support_thinking(self):
        assert supports_thinking("anthropic/claude-haiku-4.5") is False

    def test_qwen_does_not_support_thinking(self):
        assert supports_thinking("qwen/qwen3.5-397b-a17b") is False

    def test_unknown_model_does_not_support_thinking(self):
        # Backend safe default: False (don't send thinking param to unknown models — could error)
        # Intentionally opposite from frontend safe default (True — show the UI toggle)
        assert supports_thinking("some-unknown-model") is False


class TestRegistryCompleteness:
    def test_all_models_have_positive_context_window(self):
        for model_id, info in ALL_MODELS.items():
            assert info.context_window > 0, f"{model_id} has zero context window"

    def test_all_model_keys_match_ids(self):
        for model_id, info in ALL_MODELS.items():
            assert info.id == model_id, f"Key/id mismatch for {model_id}"
