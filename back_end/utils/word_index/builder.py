"""
Word index builder.

Builds or rebuilds the word_index collection for a language by streaming
all verses from bible_texts, tokenizing, and inserting one document per word.

Usage as CLI:
    python -m utils.word_index.builder --language bughotu
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from constants import Collection
from utils.word_index.tokenizer import tokenize_verse

logger = logging.getLogger(__name__)

# Cap occurrences per document to prevent oversized MongoDB docs.
# total_count still reflects the true count; occurrences is a sample.
MAX_OCCURRENCES = 1000


async def build_word_index(
    db,
    language_code: str,
) -> dict[str, Any]:
    """
    Full rebuild of word_index for a language.

    1. Drop existing entries for language_code
    2. Stream all verses from bible_texts
    3. Tokenize each verse
    4. Accumulate word → occurrences mapping
    5. Cross-reference dictionary for in_dictionary flag
    6. Bulk insert into word_index collection

    Args:
        db: MongoDBConnector instance
        language_code: Language to index

    Returns:
        {words_indexed: int, verses_processed: int, duration_ms: int}
    """
    start = time.monotonic()
    language_code = language_code.lower()

    bible_texts = db.get_collection(Collection.BIBLE_TEXTS)
    word_index_col = db.get_collection(Collection.WORD_INDEX)

    # Check if this is the base language (English uses english_text field)
    languages_col = db.get_collection(Collection.LANGUAGES)
    lang_doc = await languages_col.find_one({"language_code": language_code})
    is_base = lang_doc.get("is_base_language", False) if lang_doc else False
    text_field = "english_text" if is_base else "translated_text"

    # 1. Drop existing entries for this language
    await word_index_col.delete_many({"language_code": language_code})

    # 2. Stream all verses for this language
    query: dict[str, Any] = {"language_code": language_code}

    # Sort by canonical order for deterministic occurrence sampling
    cursor = bible_texts.find(
        query,
        {"book_code": 1, "chapter": 1, "verse": 1, text_field: 1},
    ).sort([("book_code", 1), ("chapter", 1), ("verse", 1)])

    # 3-4. Tokenize and accumulate
    word_data: dict[str, dict[str, Any]] = {}
    verses_processed = 0

    async for doc in cursor:
        text = doc.get(text_field, "")
        if not text or not text.strip():
            continue

        verses_processed += 1
        tokens = tokenize_verse(text)
        book_code = doc["book_code"]
        chapter = doc["chapter"]
        verse = doc["verse"]

        # Build context window from full token list
        for position, word in enumerate(tokens):
            if word not in word_data:
                word_data[word] = {
                    "total_count": 0,
                    "books": set(),
                    "chapters": set(),
                    "occurrences": [],
                    "first_seen": {
                        "book_code": book_code,
                        "chapter": chapter,
                        "verse": verse,
                    },
                }

            wd = word_data[word]
            wd["total_count"] += 1
            wd["books"].add(book_code)
            wd["chapters"].add(f"{book_code}:{chapter}")

            # Cap occurrences (first N by canonical order)
            if len(wd["occurrences"]) < MAX_OCCURRENCES:
                # Context snippet: 5-word window centered on this word
                start_idx = max(0, position - 2)
                end_idx = min(len(tokens), position + 3)
                snippet_words = tokens[start_idx:end_idx]
                prefix = "..." if start_idx > 0 else ""
                suffix = "..." if end_idx < len(tokens) else ""
                snippet = f"{prefix}{' '.join(snippet_words)}{suffix}"

                wd["occurrences"].append({
                    "book_code": book_code,
                    "chapter": chapter,
                    "verse": verse,
                    "position": position,
                    "context_snippet": snippet,
                })

    # 5. Cross-reference dictionary for in_dictionary flag
    dictionary_words = await _get_dictionary_words(db, language_code)

    # 6. Bulk insert
    now = datetime.now(timezone.utc)
    docs_to_insert = []

    for word, wd in word_data.items():
        docs_to_insert.append({
            "language_code": language_code,
            "word": word,
            "total_count": wd["total_count"],
            "book_count": len(wd["books"]),
            "chapter_count": len(wd["chapters"]),
            "occurrences": wd["occurrences"],
            "first_seen": wd["first_seen"],
            "in_dictionary": word in dictionary_words,
            "last_rebuilt": now,
        })

    if docs_to_insert:
        await word_index_col.insert_many(docs_to_insert)

    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        f"word_index: {language_code} — "
        f"{len(docs_to_insert)} words from {verses_processed} verses"
    )

    return {
        "words_indexed": len(docs_to_insert),
        "verses_processed": verses_processed,
        "duration_ms": duration_ms,
    }


async def sync_dictionary_flags(
    db,
    language_code: str,
    words: list[str] | None = None,
) -> int:
    """
    Targeted update of in_dictionary flags (NOT a full rebuild).

    Used after dictionary entries are added/removed. Instant (<5ms)
    compared to a 10-30 second full rebuild.

    Args:
        db: MongoDBConnector instance
        language_code: Language to update
        words: Specific words to update. If None, updates all words.

    Returns:
        Number of documents modified
    """
    word_index_col = db.get_collection(Collection.WORD_INDEX)
    dictionary_words = await _get_dictionary_words(db, language_code)

    if words:
        # Targeted: update only specified words
        modified = 0
        for word in words:
            word_lower = word.lower()
            result = await word_index_col.update_many(
                {"language_code": language_code, "word": word_lower},
                {"$set": {"in_dictionary": word_lower in dictionary_words}},
            )
            modified += result.modified_count
        return modified
    else:
        # Bulk: set all to False, then set matches to True
        await word_index_col.update_many(
            {"language_code": language_code},
            {"$set": {"in_dictionary": False}},
        )
        if dictionary_words:
            result = await word_index_col.update_many(
                {"language_code": language_code, "word": {"$in": list(dictionary_words)}},
                {"$set": {"in_dictionary": True}},
            )
            return result.modified_count
        return 0


async def _get_dictionary_words(db, language_code: str) -> set[str]:
    """Get all dictionary words for a language, lowercased, for in_dictionary matching."""
    dictionaries = db.get_collection(Collection.DICTIONARIES)

    words: set[str] = set()
    async for doc in dictionaries.find(
        {"language_code": language_code},
        {"entries.word": 1},
    ):
        for entry in doc.get("entries", []):
            word = entry.get("word", "")
            if word:
                words.add(word.lower())

    return words


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    # Add back_end to path for imports
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

    from db_connector.connection import MongoDBConnector

    parser = argparse.ArgumentParser(description="Build word index for a language")
    parser.add_argument("--language", required=True, help="Language code (e.g., bughotu)")
    args = parser.parse_args()

    async def main():
        db = MongoDBConnector()
        await db.connect()
        try:
            result = await build_word_index(db, args.language)
            print(f"Done: {result['words_indexed']} words from "
                  f"{result['verses_processed']} verses in {result['duration_ms']}ms")
        finally:
            db.close()

    asyncio.run(main())
