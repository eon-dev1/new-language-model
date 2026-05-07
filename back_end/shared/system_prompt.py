"""
System prompt for the NLM chat assistant.

Single source of truth. Edit prompts/system-prompt.md to tune LLM behavior.
This is the static instruction set — it does not contain data.
Data context from MongoDB is assembled separately by utils/chat_context.py.
"""

import pathlib
import logging

logger = logging.getLogger(__name__)

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "system-prompt.md"


def _load_prompt(path: pathlib.Path) -> str:
    """Load and strip a prompt file. Returns '' on FileNotFoundError."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.error(
            f"[system_prompt] Prompt file not found: {path}. Falling back to empty string."
        )
        return ""


def load_skill(skill_name: str) -> str | None:
    """Load a skill overlay from prompts/skills/<skill_name>/SKILL.md.

    Returns the stripped file contents, or None if the file does not exist.
    Returns None (not '') on missing — callers use None as a definitive absence signal.
    """
    path = _PROMPTS_DIR / "skills" / skill_name / "SKILL.md"
    try:
        content = path.read_text(encoding="utf-8").strip()
        logger.info(f"[system_prompt] Skill '{skill_name}' loaded: {len(content)} chars")
        return content
    except FileNotFoundError:
        logger.warning(f"[system_prompt] Skill '{skill_name}' not found: {path}")
        return None


def compose_prompt(base: str, skill: str | None = None) -> str:
    """Compose a system prompt from a base string and an optional skill overlay.

    Composition rule: base + '\\n\\n---\\n\\n' + skill
    When skill is None, returns base unchanged.
    Output is deterministic — same inputs always produce identical output (HMAC depends on this).
    """
    if skill is None:
        return base
    return f"{base}\n\n---\n\n{skill}"


SYSTEM_PROMPT = _load_prompt(_SYSTEM_PROMPT_PATH)
logger.info(f"[system_prompt] SYSTEM_PROMPT loaded: {len(SYSTEM_PROMPT)} chars")
