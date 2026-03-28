"""
System prompt for the NLM chat assistant.

Single source of truth. Edit prompts/system-prompt.md to tune LLM behavior.
This is the static instruction set — it does not contain data.
Data context from MongoDB is assembled separately by utils/chat_context.py.
"""

import pathlib
import logging

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "system-prompt.md"


def _load_prompt(path: pathlib.Path) -> str:
    """Load and strip a prompt file. Returns '' on FileNotFoundError."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logging.getLogger(__name__).error(
            f"[system_prompt] Prompt file not found: {path}. Falling back to empty string."
        )
        return ""


SYSTEM_PROMPT = _load_prompt(_SYSTEM_PROMPT_PATH)
