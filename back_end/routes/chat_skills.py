"""
Skill discovery endpoint.

GET /chat/skills — reads back_end/prompts/skills/ and returns skills
that have both a skill.json (metadata) and a non-empty SKILL.md (prompt).

Skill folders without a skill.json are silently skipped (e.g. translation-triologue).
"""

import json
import logging
import pathlib
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_SKILLS_DIR = pathlib.Path(__file__).parent.parent / "prompts" / "skills"


class SkillItem(BaseModel):
    key: str
    label: str
    views: list[str]
    prompt: str


@router.get("/chat/skills", response_model=list[SkillItem])
def list_skills() -> list[SkillItem]:
    """Return all discoverable skills from the prompts/skills directory."""
    if not _SKILLS_DIR.exists():
        return []

    skills: list[SkillItem] = []

    for folder in sorted(_SKILLS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        skill_json = folder / "skill.json"
        skill_md = folder / "SKILL.md"

        if not skill_json.exists():
            continue

        try:
            meta = json.loads(skill_json.read_text(encoding="utf-8"))
            prompt = skill_md.read_text(encoding="utf-8").strip() if skill_md.exists() else ""
            label = meta.get("label", "")
            views = meta.get("views", [])

            if not prompt or not label:
                continue

            skills.append(SkillItem(
                key=folder.name,
                label=label,
                views=views,
                prompt=prompt,
            ))
        except Exception as e:
            logger.warning(f"[chat_skills] Skipping {folder.name}: {e}")
            continue

    return skills
