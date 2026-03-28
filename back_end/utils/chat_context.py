"""
Context assembly for chat endpoint.

Given the user's current app view, fetches relevant data from MongoDB
and constructs a context block describing what the user is looking at.

This module has NO knowledge of system prompts or LLM instructions.
It only assembles data. The chat endpoint combines this with the
system prompt from shared/system_prompt.py.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Approximate char budget for assembled context (~25K tokens)
MAX_CONTEXT_CHARS = 100_000


async def assemble_context(
    db,
    language_code: str | None = None,
    book_code: str | None = None,
    chapter: int | None = None,
    view: str | None = None,
) -> str:
    """
    Build a data context block from MongoDB based on the user's current view.

    Args:
        db: MongoDBConnector instance
        language_code: Current language (if any)
        book_code: Current book (if in bible_reader)
        chapter: Current chapter (if in bible_reader)
        view: Current view ('bible_reader', 'dictionary', 'grammar', or None)

    Returns:
        Context string describing the user's current data, or empty string.
    """
    if not language_code:
        return ""

    parts = []

    lang_meta = await _get_language_metadata(db, language_code)
    if lang_meta:
        parts.append(lang_meta)

    if view == "bible_reader" and book_code and chapter:
        bible_ctx = await _get_bible_context(db, language_code, book_code, chapter)
        if bible_ctx:
            parts.append(bible_ctx)

    elif view == "dictionary":
        dict_ctx = await _get_dictionary_context(db, language_code)
        if dict_ctx:
            parts.append(dict_ctx)

    elif view == "grammar":
        grammar_ctx = await _get_grammar_context(db, language_code)
        if grammar_ctx:
            parts.append(grammar_ctx)

    if not parts:
        return ""

    result = "\n\n".join(parts)
    if len(result) > MAX_CONTEXT_CHARS:
        result = result[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated due to length]"

    return result


async def _get_language_metadata(db, language_code: str) -> str | None:
    try:
        coll = db.get_collection("languages")
        doc = await coll.find_one(
            {"language_code": language_code.lower()}
        )
        if not doc:
            return None

        name = doc.get("language_name", language_code)
        status = doc.get("status", "unknown")
        stats = doc.get("translation_stats", {})

        lines = [f"## Current Language: {name} ({language_code})", f"Status: {status}"]

        verses_translated = stats.get("verses_translated", 0)
        verses_verified = stats.get("verses_verified", 0)
        books_completed = stats.get("books_completed", 0)
        books_started = stats.get("books_started", 0)

        if books_started > 0:
            lines.append(f"Books: {books_started} started, {books_completed} completed")
        if verses_translated > 0:
            lines.append(f"Verses: {verses_translated} translated, {verses_verified} verified")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to get language metadata: {e}")
        return None


async def _get_bible_context(
    db, language_code: str, book_code: str, chapter: int
) -> str | None:
    try:
        coll = db.get_collection("bible_texts")

        english_cursor = coll.find({
            "language_code": "english",
            "book_code": book_code,
            "chapter": chapter,
        }).sort("verse", 1)
        english_verses = await english_cursor.to_list(length=200)

        target_cursor = coll.find({
            "language_code": language_code.lower(),
            "book_code": book_code,
            "chapter": chapter,
        }).sort("verse", 1)
        target_verses = await target_cursor.to_list(length=200)

        if not english_verses and not target_verses:
            return None

        target_map = {v["verse"]: v for v in target_verses}

        lines = [f"## Current View: {book_code.replace('_', ' ').title()} Chapter {chapter}"]

        for ev in english_verses:
            verse_num = ev["verse"]
            eng_text = ev.get("text", "")
            tv = target_map.get(verse_num)
            target_text = tv.get("text", "") if tv else "[not yet translated]"

            lines.append(f"v{verse_num} EN: {eng_text}")
            lines.append(f"v{verse_num} {language_code.upper()}: {target_text}")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to get bible context: {e}")
        return None


async def _get_dictionary_context(db, language_code: str) -> str | None:
    try:
        coll = db.get_collection("dictionaries")
        doc = await coll.find_one(
            {"language_code": language_code.lower()}
        )
        if not doc:
            return None

        entries = doc.get("entries", [])

        if not entries:
            return None

        sample = entries[:50]

        lines = [f"## Dictionary Sample ({len(sample)} of {len(entries)} entries)"]
        for entry in sample:
            word = entry.get("word", "?")
            defn = entry.get("definition", "")
            pos = entry.get("part_of_speech", "")
            lines.append(f"- {word} ({pos}): {defn}")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to get dictionary context: {e}")
        return None


async def _get_grammar_context(db, language_code: str) -> str | None:
    try:
        coll = db.get_collection("grammar_systems")
        doc = await coll.find_one(
            {"language_code": language_code.lower()}
        )
        if not doc:
            return None

        categories = doc.get("categories", {})
        if not categories:
            return None

        lines = ["## Grammar System Summary"]

        for cat_name, cat_data in categories.items():
            if not isinstance(cat_data, dict):
                continue

            desc = cat_data.get("description", "")
            subcats = cat_data.get("subcategories", [])

            if desc or subcats:
                lines.append(f"\n### {cat_name.title()}")
                if desc:
                    lines.append(desc[:500])
                if subcats:
                    for sc in subcats[:5]:
                        sc_name = sc.get("name", "") if isinstance(sc, dict) else str(sc)
                        lines.append(f"  - {sc_name}")

        return "\n".join(lines) if len(lines) > 1 else None
    except Exception as e:
        logger.warning(f"Failed to get grammar context: {e}")
        return None
