"""
Phrase index builder.

Builds or rebuilds the phrase_index collection for a language by streaming
all verses from bible_texts, tokenizing, generating 4-grams, and inserting
one document per recurring 4-gram (df >= 2).

The stored phrase form is canonical:
    phrase = " ".join(tokenize_verse(text))
Builder and MCP tool (get_phrase_context) MUST construct lookup keys with
the same form. A mismatch is the most plausible silent-failure mode.

For non-base (target) languages, only verses with human_verified=True
contribute — this is what protects the consistency signal.

Usage as CLI:
    python -m utils.phrase_index.builder --language bughotu

DO NOT run the CLI while the backend is active: the in-app scheduler and
CLI both delete_many then insert_many on the same language_code without a
shared cross-process lock, and a collision can leave the index in a partial
state (DuplicateKeyError from the unique (language_code, phrase) index).
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from constants import Collection
from utils.word_index.tokenizer import tokenize_verse

logger = logging.getLogger(__name__)

# 4-gram size — fixed. The tool only generates 4-grams from input text, so
# emitting anything with n != 4 would be unreachable from the query path.
N_PHRASE = 4

# Minimum df to emit. Non-recurring phrases are noise for a consistency signal.
PHRASE_MIN_DF = 2

# Cap on stored locations per phrase. Mirrors word_index MAX_OCCURRENCES.
# NOTE: this caps the stored list only. `df` is tracked via a separate counter
# and is NOT bounded by MAX_LOCATIONS — see the reconciliation block below.
MAX_LOCATIONS = 1000


async def build_phrase_index(
    db,
    language_code: str,
) -> dict[str, Any]:
    """
    Full rebuild of phrase_index for a language.

    1. Filter verses:
       - base language (English): all verses
       - target languages: human_verified=True only
    2. Stream in canonical order (book_code, chapter, verse)
    3. Tokenize each verse, generate 4-grams
    4. Track distinct verse-df per token (for min_word_df)
    5. Track df + locations per 4-gram, deduplicated by verse ref
    6. Emit one document per 4-gram with df >= PHRASE_MIN_DF

    Args:
        db: MongoDBConnector instance
        language_code: Language to index

    Returns:
        {phrases_emitted: int, verses_processed: int, duration_ms: int}
    """
    start = time.monotonic()
    language_code = language_code.lower()

    bible_texts = db.get_collection(Collection.BIBLE_TEXTS)
    phrase_index_col = db.get_collection(Collection.PHRASE_INDEX)

    # Base language check — mirrors word_index/builder.py:54-58
    languages_col = db.get_collection(Collection.LANGUAGES)
    lang_doc = await languages_col.find_one({"language_code": language_code})
    is_base = lang_doc.get("is_base_language", False) if lang_doc else False
    text_field = "english_text" if is_base else "translated_text"

    # Idempotent rebuild — drop existing entries for this language only.
    await phrase_index_col.delete_many({"language_code": language_code})

    # Verified-only filter for non-base languages — the consistency signal
    # depends on only committed renderings contributing to the index.
    query: dict[str, Any] = {"language_code": language_code}
    if not is_base:
        query["human_verified"] = True

    cursor = bible_texts.find(
        query,
        {"book_code": 1, "chapter": 1, "verse": 1, text_field: 1},
    ).sort([("book_code", 1), ("chapter", 1), ("verse", 1)])

    # Per-token df (distinct verses containing the token) — for min_word_df.
    # Tracked as set of verse-id keys during the pass, collapsed to counts
    # at the end to bound peak memory.
    word_df_sets: dict[str, set[tuple[str, int, int]]] = {}

    # Per-phrase state.
    # df: distinct verses containing this 4-gram (NOT bounded by MAX_LOCATIONS).
    # locations: capped sample of verse refs in canonical order.
    phrase_df: dict[str, int] = {}
    phrase_locations: dict[str, list[dict[str, Any]]] = {}

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
        verse_key = (book_code, chapter, verse)

        # Word-df tracking (distinct verses per token)
        for tok in tokens:
            s = word_df_sets.get(tok)
            if s is None:
                s = set()
                word_df_sets[tok] = s
            s.add(verse_key)

        # Verses with < N tokens produce no grams.
        # NO short-verse fallback: the tool only generates n=4 grams from input,
        # so any n<4 doc the builder emitted would be unreachable from the query.
        if len(tokens) < N_PHRASE:
            continue

        # 4-grams within this verse — order matters for dedup ("first time seen
        # in this verse" test = "locations[-1] != verse_ref"). Intra-verse
        # repeats of the same 4-gram must count df once (a verse containing the
        # same formula twice is still one verse-document).
        for i in range(len(tokens) - N_PHRASE + 1):
            phrase = " ".join(tokens[i:i + N_PHRASE])

            locs = phrase_locations.get(phrase)
            if locs is None:
                locs = []
                phrase_locations[phrase] = locs
                phrase_df[phrase] = 0

            last = locs[-1] if locs else None
            new_verse = (
                last is None
                or last["book_code"] != book_code
                or last["chapter"] != chapter
                or last["verse"] != verse
            )
            if new_verse:
                # df counter is always incremented — NOT derived from
                # len(locations). Naive `df = len(locations)` under-counts by
                # (df - MAX_LOCATIONS) once past the cap.
                phrase_df[phrase] += 1
                if len(locs) < MAX_LOCATIONS:
                    locs.append({
                        "book_code": book_code,
                        "chapter": chapter,
                        "verse": verse,
                    })

    # Collapse word_df sets to counts (bound memory before doc construction).
    word_df: dict[str, int] = {tok: len(s) for tok, s in word_df_sets.items()}
    word_df_sets.clear()

    # Emit one doc per recurring 4-gram.
    now = datetime.now(timezone.utc)
    docs_to_insert: list[dict[str, Any]] = []

    for phrase, df in phrase_df.items():
        if df < PHRASE_MIN_DF:
            continue

        tokens = phrase.split(" ")
        # min_word_df is the rarest token's word-df — the distinctiveness score
        # the tool filters on. Stored, not thresholded at build time.
        min_wdf = min(word_df.get(t, 0) for t in tokens)

        docs_to_insert.append({
            "language_code": language_code,
            "phrase": phrase,
            "n": N_PHRASE,
            "df": df,
            "min_word_df": min_wdf,
            "locations": phrase_locations[phrase],
            "last_rebuilt": now,
        })

    # Empty-build guard — motor's insert_many([]) raises. This path is real
    # for verified-only target builds with zero verified verses.
    if docs_to_insert:
        await phrase_index_col.insert_many(docs_to_insert)

    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        f"phrase_index: {language_code} — "
        f"{len(docs_to_insert)} phrases from {verses_processed} verses "
        f"in {duration_ms}ms"
    )

    return {
        "phrases_emitted": len(docs_to_insert),
        "verses_processed": verses_processed,
        "duration_ms": duration_ms,
    }


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    # Add back_end to path for imports (mirrors word_index/builder.py)
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

    from db_connector.connection import MongoDBConnector

    parser = argparse.ArgumentParser(
        description=(
            "Build phrase index for a language. "
            "WARNING: Do not run while the backend is active — the in-app "
            "scheduler and this CLI both delete_many then insert_many on the "
            "same language_code without a shared cross-process lock. A "
            "collision can leave phrase_index with a DuplicateKeyError from "
            "the unique (language_code, phrase) index and partial state from "
            "whichever insert won the race."
        )
    )
    parser.add_argument("--language", required=True, help="Language code (e.g., bughotu)")
    args = parser.parse_args()

    async def main():
        db = MongoDBConnector()
        await db.connect()
        try:
            result = await build_phrase_index(db, args.language)
            print(
                f"Done: {result['phrases_emitted']} phrases from "
                f"{result['verses_processed']} verses in {result['duration_ms']}ms"
            )
        finally:
            await db.disconnect()

    asyncio.run(main())
