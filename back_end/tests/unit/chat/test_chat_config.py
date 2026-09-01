"""
Tests for shared/chat_config.py

Failure points targeted:
- Config file doesn't exist → should return defaults, not crash
- Corrupt JSON → should return defaults, not crash
- Unknown keys ignored on update
- API key masking in public config
- Legacy migration: anthropic configs are migrated to openrouter
- Local-user guard: local provider is NOT coerced by migration
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
        assert config["llm_provider"] == "openrouter"
        assert "anthropic_api_key" not in config
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
        assert config["openrouter_model"] == DEFAULT_CONFIG["openrouter_model"]


class TestUpdateConfig:
    def test_updates_known_keys(self, tmp_config):
        result = update_config({"llm_provider": "local"})
        assert result["llm_provider"] == "local"
        reloaded = load_config()
        assert reloaded["llm_provider"] == "local"

    def test_ignores_unknown_keys(self, tmp_config):
        result = update_config({"unknown_key": "value", "llm_provider": "local"})
        assert "unknown_key" not in result
        assert result["llm_provider"] == "local"

    def test_anthropic_keys_rejected_by_allowlist(self, tmp_config):
        """Post-migration, anthropic_api_key is not in DEFAULT_CONFIG and cannot be set."""
        result = update_config({"anthropic_api_key": "sk-ant-new"})
        assert "anthropic_api_key" not in result


class TestGetPublicConfig:
    def test_masks_openrouter_key(self, tmp_config):
        save_config({**DEFAULT_CONFIG, "openrouter_api_key": "sk-or-1234567890abcdef"})
        public = get_public_config()
        assert public["has_openrouter_key"] is True
        assert public["openrouter_key_preview"] == "...cdef"
        assert "openrouter_api_key" not in public

    def test_empty_openrouter_key(self, tmp_config):
        public = get_public_config()
        assert public["has_openrouter_key"] is False
        assert public["openrouter_key_preview"] == ""

    def test_short_openrouter_key(self, tmp_config):
        save_config({**DEFAULT_CONFIG, "openrouter_api_key": "abc"})
        public = get_public_config()
        assert public["has_openrouter_key"] is True
        assert public["openrouter_key_preview"] == ""  # Too short to preview

    def test_no_anthropic_fields_in_public_config(self, tmp_config):
        public = get_public_config()
        assert "anthropic_model" not in public
        assert "has_api_key" not in public
        assert "api_key_preview" not in public


class TestLegacyMigration:
    def test_anthropic_config_migrated_to_openrouter(self, tmp_config):
        """Existing anthropic config is migrated: provider coerced, secrets popped."""
        legacy = {
            "llm_provider": "anthropic",
            "anthropic_api_key": "sk-ant-secret123",
            "anthropic_model": "claude-sonnet-4-6",
            "openrouter_api_key": "",
            "openrouter_model": "anthropic/claude-sonnet-4.6",
        }
        tmp_config.write_text(json.dumps(legacy), encoding='utf-8')

        config = load_config()
        # Return value must be clean
        assert config["llm_provider"] == "openrouter"
        assert "anthropic_api_key" not in config
        assert "anthropic_model" not in config

        # Disk must also be clean
        disk = json.loads(tmp_config.read_text(encoding='utf-8'))
        assert "anthropic_api_key" not in disk
        assert "anthropic_model" not in disk
        assert disk["llm_provider"] == "openrouter"

    def test_local_user_not_coerced(self, tmp_config):
        """Local user with stale anthropic keys: provider stays local, keys still popped."""
        legacy = {
            "llm_provider": "local",
            "anthropic_api_key": "sk-ant-stale",
            "anthropic_model": "claude-sonnet-4-6",
            "local_base_url": "http://127.0.0.1:8080",
        }
        tmp_config.write_text(json.dumps(legacy), encoding='utf-8')

        config = load_config()
        assert config["llm_provider"] == "local"  # NOT coerced to openrouter
        assert "anthropic_api_key" not in config
        assert "anthropic_model" not in config

    def test_already_openrouter_with_stale_key(self, tmp_config):
        """User already on openrouter but with stale anthropic_api_key on disk."""
        legacy = {
            "llm_provider": "openrouter",
            "anthropic_api_key": "sk-ant-leftover",
            "openrouter_api_key": "sk-or-active",
        }
        tmp_config.write_text(json.dumps(legacy), encoding='utf-8')

        config = load_config()
        assert config["llm_provider"] == "openrouter"
        assert "anthropic_api_key" not in config
        assert config["openrouter_api_key"] == "sk-or-active"

    def test_runtime_coercion_heals_stale_provider(self, tmp_config):
        """A direct API POST of llm_provider:"anthropic" is coerced in-memory."""
        stale = {"llm_provider": "anthropic", "openrouter_api_key": "sk-or-valid"}
        tmp_config.write_text(json.dumps(stale), encoding='utf-8')

        config = load_config()
        assert config["llm_provider"] == "openrouter"

    def test_migration_idempotent(self, tmp_config):
        """Calling load_config twice after migration doesn't re-write or error."""
        legacy = {
            "llm_provider": "anthropic",
            "anthropic_api_key": "sk-ant-x",
        }
        tmp_config.write_text(json.dumps(legacy), encoding='utf-8')

        config1 = load_config()
        config2 = load_config()
        assert config1["llm_provider"] == config2["llm_provider"] == "openrouter"
