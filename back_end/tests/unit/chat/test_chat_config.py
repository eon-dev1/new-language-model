"""
Tests for shared/chat_config.py

Failure points targeted:
- Config file doesn't exist → should return defaults, not crash
- Corrupt JSON → should return defaults, not crash
- Unknown keys ignored on update
- API key masking in public config
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from shared.chat_config import (
    load_config, save_config, update_config, get_public_config,
    DEFAULT_CONFIG, CONFIG_FILE,
)


@pytest.fixture
def tmp_config(tmp_path):
    """Redirect config to a temp directory."""
    config_file = tmp_path / "chat_config.json"
    with patch("shared.chat_config.CONFIG_DIR", tmp_path), \
         patch("shared.chat_config.CONFIG_FILE", config_file):
        yield config_file


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_config):
        config = load_config()
        assert config["llm_provider"] == "anthropic"
        assert config["anthropic_api_key"] == ""
        # Should also create the file
        assert tmp_config.exists()

    def test_corrupt_json_returns_defaults(self, tmp_config):
        tmp_config.write_text("{not valid json!!!", encoding='utf-8')
        config = load_config()
        assert config == DEFAULT_CONFIG

    def test_merges_new_keys_with_existing(self, tmp_config):
        """If config file is missing a key added in a newer version, it gets the default."""
        tmp_config.write_text(json.dumps({"llm_provider": "local"}), encoding='utf-8')
        config = load_config()
        assert config["llm_provider"] == "local"
        assert config["anthropic_model"] == DEFAULT_CONFIG["anthropic_model"]


class TestUpdateConfig:
    def test_updates_known_keys(self, tmp_config):
        result = update_config({"llm_provider": "local"})
        assert result["llm_provider"] == "local"
        # Verify persisted
        reloaded = load_config()
        assert reloaded["llm_provider"] == "local"

    def test_ignores_unknown_keys(self, tmp_config):
        result = update_config({"unknown_key": "value", "llm_provider": "local"})
        assert "unknown_key" not in result
        assert result["llm_provider"] == "local"


class TestGetPublicConfig:
    def test_masks_api_key(self, tmp_config):
        save_config({**DEFAULT_CONFIG, "anthropic_api_key": "sk-ant-1234567890abcdef"})
        public = get_public_config()
        assert public["has_api_key"] is True
        assert public["api_key_preview"] == "...cdef"
        assert "anthropic_api_key" not in public

    def test_empty_api_key(self, tmp_config):
        public = get_public_config()
        assert public["has_api_key"] is False
        assert public["api_key_preview"] == ""

    def test_short_api_key(self, tmp_config):
        save_config({**DEFAULT_CONFIG, "anthropic_api_key": "abc"})
        public = get_public_config()
        assert public["has_api_key"] is True
        assert public["api_key_preview"] == ""  # Too short to preview
