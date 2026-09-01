"""
Tests for shared/system_prompt.py

Covers:
- SYSTEM_PROMPT loads correctly from file
- load_skill() returns content for existing skills, None for missing
- compose_prompt() assembles base + skill and is deterministic
"""

import pathlib

import shared.system_prompt as sp


# ── SYSTEM_PROMPT ──────────────────────────────────────────────────────────────

def test_system_prompt_loads():
    assert isinstance(sp.SYSTEM_PROMPT, str)
    assert len(sp.SYSTEM_PROMPT) > 0


# ── load_skill ─────────────────────────────────────────────────────────────────

def test_load_skill_existing(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Batch mechanics content", encoding="utf-8")

    monkeypatch.setattr(sp, "_PROMPTS_DIR", tmp_path)
    result = sp.load_skill("test-skill")
    assert result == "Batch mechanics content"


def test_load_skill_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "_PROMPTS_DIR", tmp_path)
    result = sp.load_skill("nonexistent-skill")
    assert result is None


# ── compose_prompt ─────────────────────────────────────────────────────────────

def test_compose_prompt_base_only():
    base = "Base prompt content"
    result = sp.compose_prompt(base)
    assert result == base


def test_compose_prompt_with_skill():
    base = "Base prompt"
    skill = "Skill overlay"
    result = sp.compose_prompt(base, skill=skill)
    assert result.startswith(base)
    assert skill in result
    # Separator present
    assert "---" in result
