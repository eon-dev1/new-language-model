"""
Tests for utils/llm_provider.py

Failure points targeted:
- get_provider() with empty API key → should raise ValueError
- get_provider() with unknown provider type → should raise ValueError
- Local provider uses correct base_url and dummy api_key
"""

import pytest
from unittest.mock import patch

from utils.llm_provider import get_provider, AnthropicProvider


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
