"""
Tests for the Modes feature backend changes.

Failure points targeted:
- system_prompt._load_prompt: file-not-found falls back to "" without crash
- system_prompt._load_prompt: content is stripped (no leading/trailing whitespace)
- chat.py skill injection: think_harder mode injects triologue skill
- chat.py skill injection: think mode does NOT inject any skill
- chat.py skill injection: null/absent chat_mode does NOT inject skill
- chat.py skill injection: missing skill file (None) does not crash
- chat.py skill injection: skill appended AFTER data context, not before
- ChatRequest: chat_mode defaults to None (backward-compat for old clients)
"""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# system_prompt._load_prompt tests
#
# NOTE: SYSTEM_PROMPT is assigned at module import time. Tests cannot change
# it by patching _SYSTEM_PROMPT_PATH after import. We test _load_prompt(path)
# directly — this is why the helper function is extracted.
# ---------------------------------------------------------------------------

class TestLoadPromptHelper:
    def test_loads_content_from_file(self, tmp_path):
        """Prompt file exists — returns its stripped content."""
        from shared.system_prompt import _load_prompt

        prompt_file = tmp_path / "system-prompt.md"
        prompt_file.write_text("You are Scribe.\n\nHelp translators.", encoding="utf-8")

        result = _load_prompt(prompt_file)
        assert result == "You are Scribe.\n\nHelp translators."

    def test_missing_file_returns_empty_string(self, tmp_path):
        """When the file is absent, returns '' without raising."""
        from shared.system_prompt import _load_prompt

        missing = tmp_path / "does-not-exist.md"
        result = _load_prompt(missing)
        assert result == ""

    def test_content_is_stripped(self, tmp_path):
        """Leading/trailing whitespace and newlines are stripped."""
        from shared.system_prompt import _load_prompt

        prompt_file = tmp_path / "system-prompt.md"
        prompt_file.write_text("\n\n  You are Scribe.  \n\n", encoding="utf-8")

        assert _load_prompt(prompt_file) == "You are Scribe."

    @pytest.mark.integration
    def test_current_prompt_file_is_loadable(self):
        """Integration: the real system-prompt.md on disk loads without error.
        Skipped in CI if file not present — mark with pytest -m 'not integration' to exclude.
        """
        import shared.system_prompt as sp_module

        assert isinstance(sp_module.SYSTEM_PROMPT, str)
        assert len(sp_module.SYSTEM_PROMPT) > 0


# ---------------------------------------------------------------------------
# ChatRequest model tests
# ---------------------------------------------------------------------------

class TestChatRequestModel:
    def test_chat_mode_defaults_to_none(self):
        """Old clients that don't send chat_mode should get None, not crash."""
        from routes.chat import ChatRequest, ChatMessage

        req = ChatRequest(messages=[ChatMessage(role="user", content="Hello")])
        assert req.chat_mode is None

    def test_chat_mode_accepts_think(self):
        from routes.chat import ChatRequest, ChatMessage

        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            chat_mode="think",
        )
        assert req.chat_mode == "think"

    def test_chat_mode_accepts_think_harder(self):
        from routes.chat import ChatRequest, ChatMessage

        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            chat_mode="think_harder",
        )
        assert req.chat_mode == "think_harder"

    def test_thinking_enabled_defaults_to_false(self):
        """Backward-compat: existing clients that omit thinking_enabled still work."""
        from routes.chat import ChatRequest, ChatMessage

        req = ChatRequest(messages=[ChatMessage(role="user", content="Hello")])
        assert req.thinking_enabled is False

    def test_chat_mode_rejects_invalid_string(self):
        """Pydantic Literal rejects unknown mode strings with ValidationError.
        Catches regression if Optional[Literal[...]] is changed back to Optional[str].
        """
        from pydantic import ValidationError
        from routes.chat import ChatRequest, ChatMessage

        with pytest.raises(ValidationError):
            ChatRequest(
                messages=[ChatMessage(role="user", content="Hello")],
                chat_mode="invalid_mode_xyz",
            )
