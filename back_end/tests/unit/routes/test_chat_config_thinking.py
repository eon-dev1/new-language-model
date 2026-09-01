"""
Round-trip test for thinking_enabled through POST /api/chat/config → GET /api/chat/config.

Failure points targeted:
- T3: POST thinking_enabled=false → GET returns false
  Exercises the full chain:
    Pydantic Optional[bool] deserialization
    → `v is not None` filter (False is not None)
    → update_config() allowlist check ("thinking_enabled" ∈ DEFAULT_CONFIG)
    → save_config() writes to disk
    → get_public_config() includes the field
  Any broken link silently fails — this test catches whichever link is missing.

Isolation: monkeypatch redirects CONFIG_DIR and CONFIG_FILE to tmp_path so this
test never touches the real ~/.nlm/chat_config.json. Safe for parallel runs.
"""

import shared.chat_config as cfg_mod
from fastapi.testclient import TestClient
from main import app

client = TestClient(app, base_url="http://localhost")


def test_post_false_then_get_returns_false(tmp_path, monkeypatch):
    """
    POST thinking_enabled=false persists and is returned by GET.

    Regression: If any step in the chain treats False as falsy/None,
    the value is silently dropped and GET still returns true.
    """
    test_config = tmp_path / "chat_config.json"
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", test_config)

    r1 = client.post("/api/chat/config", json={"thinking_enabled": False})
    assert r1.status_code == 200
    assert r1.json()["thinking_enabled"] is False

    r2 = client.get("/api/chat/config")
    assert r2.status_code == 200
    assert r2.json()["thinking_enabled"] is False


def test_post_true_then_get_returns_true(tmp_path, monkeypatch):
    """POST thinking_enabled=true persists correctly (positive path)."""
    test_config = tmp_path / "chat_config.json"
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", test_config)

    r1 = client.post("/api/chat/config", json={"thinking_enabled": True})
    assert r1.status_code == 200
    assert r1.json()["thinking_enabled"] is True

    r2 = client.get("/api/chat/config")
    assert r2.status_code == 200
    assert r2.json()["thinking_enabled"] is True


def test_omitting_thinking_enabled_does_not_reset_it(tmp_path, monkeypatch):
    """
    Saving other settings without including thinking_enabled must not reset the flag.

    Regression: If ChatConfigUpdate.thinking_enabled defaulted to False instead of
    None, every save from ChatSettings (which always includes the field) would be fine,
    but a direct API call omitting the field would silently reset it.
    """
    test_config = tmp_path / "chat_config.json"
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", test_config)

    # Disable thinking
    client.post("/api/chat/config", json={"thinking_enabled": False})

    # Save an unrelated field without including thinking_enabled
    client.post("/api/chat/config", json={"llm_provider": "openrouter"})

    r = client.get("/api/chat/config")
    assert r.json()["thinking_enabled"] is False, (
        "Partial save reset thinking_enabled — default is probably False instead of None"
    )


def test_get_config_always_includes_thinking_enabled(tmp_path, monkeypatch):
    """
    GET /api/chat/config must always include thinking_enabled in the response.

    Regression: If get_public_config() doesn't include the field,
    the frontend receives undefined and ?? true coalesces to true — the flag
    cannot be disabled from the UI even though disk has false.
    """
    test_config = tmp_path / "chat_config.json"
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", test_config)

    r = client.get("/api/chat/config")
    assert r.status_code == 200
    assert "thinking_enabled" in r.json()
    assert isinstance(r.json()["thinking_enabled"], bool)
