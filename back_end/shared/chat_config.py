"""
Chat configuration management.

Stores LLM provider settings in a JSON file outside the codebase.
API keys are stored in the system .nlm directory (~/.nlm/chat_config.json),
not in the project directory, to prevent accidental commits.

Config file location: ~/.nlm/chat_config.json
"""

import json
import logging
import stat
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".nlm"
CONFIG_FILE = CONFIG_DIR / "chat_config.json"

DEFAULT_CONFIG = {
    "llm_provider": "anthropic",
    "anthropic_api_key": "",
    "anthropic_model": "claude-sonnet-4-6",
    "local_base_url": "http://127.0.0.1:8080",
    "local_model": "default",
    "local_context_window": 128000,
    "dev_features": {},
}


def _ensure_config_dir() -> None:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)  # owner-only (mkdir mode param is unreliable with parents=True)


def load_config() -> dict[str, Any]:
    """Load chat config from disk, creating default if missing."""
    _ensure_config_dir()

    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        data = json.loads(CONFIG_FILE.read_text())
        # Merge with defaults to handle new keys added in future versions
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load chat config, using defaults: {e}")
        return dict(DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    """Save chat config to disk."""
    _ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600 — owner read/write only


def update_config(updates: dict[str, Any]) -> dict[str, Any]:
    """
    Merge updates into existing config and save.

    Args:
        updates: Key-value pairs to update (only known keys are accepted)

    Returns:
        The full updated config
    """
    config = load_config()

    for key, value in updates.items():
        if key in DEFAULT_CONFIG:
            config[key] = value
        else:
            logger.warning(f"Ignoring unknown config key: {key}")

    save_config(config)
    return config


def get_public_config() -> dict[str, Any]:
    """
    Get config safe for sending to the frontend.
    Masks the API key -- never expose the full key to the renderer.
    """
    config = load_config()
    api_key = config.get("anthropic_api_key", "")

    return {
        "llm_provider": config["llm_provider"],
        "anthropic_model": config["anthropic_model"],
        "has_api_key": bool(api_key),
        "api_key_preview": f"...{api_key[-4:]}" if len(api_key) > 4 else "",
        "local_base_url": config["local_base_url"],
        "local_model": config["local_model"],
        "local_context_window": config.get("local_context_window", 128000),
    }
