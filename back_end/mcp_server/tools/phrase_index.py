"""
Phrase index MCP tool: get_phrase_context.

One parameterized tool serving two use cases:

  (a) Cross-lingual reuse. AI is translating an English verse; pass the
      English text with language_code="english" and location_text_language
      set to the target — get English 4-grams plus verified target
      translations at other locations for pattern-matching.

  (b) Intra-target consistency. AI has a target-language draft; pass the
      draft with language_code=<target> and default location_text_language
      — get target 4-grams plus verified target text at other locations.

The stored phrase form is canonical:
    phrase = " ".join(tokenize_verse(text))
This tool MUST build lookup keys with the exact same form as the builder.
A mismatch is the most plausible silent-failure mode.
"""

from typing import Any

from constants import Collection
from mcp_server.tools.base import (
    ToolError,
    error_response,
    validate_language,
)
from utils.word_index.tokenizer import tokenize_verse

# n-gram size — must match utils/phrase_index/builder.py N_PHRASE.
N_PHRASE = 4

# Input size guards. MAX_TEXT_CHARS is well under the 16 MB BSON ceiling
# and the LLM's natural per-call budget (~50K chars ≈ a long chapter).
MAX_TEXT_CHARS = 50_000
# Bounds the $in payload and the downstream result set. Enforced after
# dedup so a huge repeated-token blob doesn't slip through.
MAX_UNIQUE_4GRAMS = 5_000
# validate_language regex-compiles the value — an arbitrarily long string
# is a cheap denial vector.
MAX_LANGUAGE_CODE_LEN = 64


async def get_phrase_context(
    db,
    language_code: str,
    text: str,
    location_text_language: str | None = None,
    book_code: str | None = None,
    chapter: int | None = None,
    verse: int | None = None,
    min_word_df_max: int = 200,
    max_locations_per_phrase: int = 10,
) -> dict[str, Any]:
    """
    Find recurring distinctive 4-grams in `text` and return where else they
    appear in the corpus, with verified text at those locations.

    Args:
        db: MongoDBConnector instance
        language_code: Which phrase_index to query. For source-side reuse
            (cross-lingual), pass "english". For intra-target consistency,
            pass the target language code. Must match the language of `text`.
        text: Text to scan for recurring 4-grams; must be in `language_code`.
        location_text_language: Language to fetch text in at each location.
            Defaults to language_code. Set to a different language for
            cross-lingual reuse (e.g., scan English, fetch target).
        book_code, chapter, verse: Optional self-reference. If any is set,
            all three must be set; the tuple is excluded from returned
            locations. book_code is lowercased on entry to match stored form.
        min_word_df_max: Scaffolding filter — keep only phrases whose rarest
            token appears in <= N verses. Default 200 (empirically drops
            "the children of israel"-style phrases where "israel" is
            everywhere). Use 50 for the most distinctive only.
        max_locations_per_phrase: Cap locations per phrase (default 10).

    Returns:
        {phrase_language, location_text_language, self_ref, phrases: [...]}
        with phrases ordered by min_word_df asc, df desc. Empty phrases list
        is a normal result (no recurring distinctive matches).
    """
    try:
        # Input size guards — check BEFORE any DB / regex work.
        if len(text) > MAX_TEXT_CHARS:
            raise ToolError(
                "invalid_input",
                f"text length {len(text)} exceeds max {MAX_TEXT_CHARS}",
                {"len": len(text), "max": MAX_TEXT_CHARS},
            )
        if len(language_code) > MAX_LANGUAGE_CODE_LEN:
            raise ToolError(
                "invalid_input",
                f"language_code length exceeds max {MAX_LANGUAGE_CODE_LEN}",
                {"len": len(language_code), "max": MAX_LANGUAGE_CODE_LEN},
            )
        if location_text_language is not None and len(location_text_language) > MAX_LANGUAGE_CODE_LEN:
            raise ToolError(
                "invalid_input",
                f"location_text_language length exceeds max {MAX_LANGUAGE_CODE_LEN}",
                {"len": len(location_text_language), "max": MAX_LANGUAGE_CODE_LEN},
            )

        # Partial self-ref guard — all-or-nothing. A partial tuple would
        # silently produce a no-op exclusion (no stored location matches
        # the partial tuple), masking caller intent.
        self_ref_parts = (book_code, chapter, verse)
        if any(p is not None for p in self_ref_parts) and not all(p is not None for p in self_ref_parts):
            raise ToolError(
                "invalid_input",
                "self-ref requires all of book_code, chapter, verse, or none of them",
                {"book_code": book_code, "chapter": chapter, "verse": verse},
            )

        # Validate languages. validate_language is case-insensitive, but the
        # stored docs are lowercase, so we MUST normalize after validation —
        # otherwise a caller passing "Bughotu" silently matches zero docs.
        await validate_language(db, language_code)
        language_code = language_code.lower()

        if location_text_language is not None:
            if location_text_language.lower() != language_code:
                await validate_language(db, location_text_language)
            location_text_language = location_text_language.lower()
        else:
            location_text_language = language_code

        # Lowercase book_code on entry so self-ref exclusion matches the
        # stored canonical form. An LLM passing "Leviticus" would otherwise
        # silently miss the exclusion.
        if book_code is not None:
            book_code = book_code.lower()

        # Whether the location-text language uses english_text vs translated_text,
        # and whether to filter human_verified.
        languages_col = db.get_collection(Collection.LANGUAGES)
        loc_lang_doc = await languages_col.find_one({"language_code": location_text_language})
        loc_is_base = loc_lang_doc.get("is_base_language", False) if loc_lang_doc else False
        loc_text_field = "english_text" if loc_is_base else "translated_text"

        # Tokenize input, generate 4-grams, dedup preserving first-occurrence
        # order. Canonical form MUST match the builder's " ".join(tokens).
        tokens = tokenize_verse(text)
        seen: set[str] = set()
        unique_4grams: list[str] = []
        for i in range(len(tokens) - N_PHRASE + 1):
            phrase = " ".join(tokens[i:i + N_PHRASE])
            if phrase not in seen:
                seen.add(phrase)
                unique_4grams.append(phrase)

        if not unique_4grams:
            return {
                "phrase_language": language_code,
                "location_text_language": location_text_language,
                "self_ref": _self_ref_dict(book_code, chapter, verse),
                "phrases": [],
            }

        if len(unique_4grams) > MAX_UNIQUE_4GRAMS:
            raise ToolError(
                "invalid_input",
                f"unique 4-gram count {len(unique_4grams)} exceeds max {MAX_UNIQUE_4GRAMS}",
                {"unique_4grams": len(unique_4grams), "max": MAX_UNIQUE_4GRAMS},
            )

        # One batched phrase_index query. Misses (non-recurring phrases) just
        # don't come back. min_word_df filter piggy-backs on the same query.
        phrase_col = db.get_collection(Collection.PHRASE_INDEX)
        phrase_cursor = phrase_col.find({
            "language_code": language_code,
            "phrase": {"$in": unique_4grams},
            "min_word_df": {"$lte": min_word_df_max},
        })

        phrase_docs: list[dict[str, Any]] = []
        async for doc in phrase_cursor:
            phrase_docs.append(doc)

        if not phrase_docs:
            return {
                "phrase_language": language_code,
                "location_text_language": location_text_language,
                "self_ref": _self_ref_dict(book_code, chapter, verse),
                "phrases": [],
            }

        # For each phrase, take an oversampled candidate slice. Canonical
        # order is already how locations are stored. The oversample protects
        # cross-lingual queries where the canonical-first locations may all
        # be unverified in the target language — which would otherwise
        # return zero despite verified renderings existing later.
        oversample = max(3 * max_locations_per_phrase, 30)
        candidate_refs: set[tuple[str, int, int]] = set()
        per_phrase_candidates: dict[str, list[dict[str, Any]]] = {}

        for doc in phrase_docs:
            phrase = doc["phrase"]
            picks: list[dict[str, Any]] = []
            for loc in doc.get("locations", []):
                if (
                    book_code is not None
                    and loc["book_code"] == book_code
                    and loc["chapter"] == chapter
                    and loc["verse"] == verse
                ):
                    continue
                picks.append(loc)
                candidate_refs.add((loc["book_code"], loc["chapter"], loc["verse"]))
                if len(picks) >= oversample:
                    break
            per_phrase_candidates[phrase] = picks

        # One batched bible_texts query. $or over the (book_code, chapter,
        # verse) triples is index-supported by the existing compound unique
        # index `verse_lookup` on bible_texts. Empty candidate set is
        # possible if every phrase's locations were the self-ref only.
        text_map: dict[tuple[str, int, int], str] = {}
        if candidate_refs:
            bible_texts = db.get_collection(Collection.BIBLE_TEXTS)
            or_clauses = [
                {"book_code": ref[0], "chapter": ref[1], "verse": ref[2]}
                for ref in candidate_refs
            ]
            bt_query: dict[str, Any] = {
                "language_code": location_text_language,
                "$or": or_clauses,
            }
            # Verified-only filter when location text is NOT the base language.
            # Base language (English) has no human_verified field on records
            # loaded via load_base_language.py.
            if not loc_is_base:
                bt_query["human_verified"] = True

            projection = {
                "book_code": 1,
                "chapter": 1,
                "verse": 1,
                loc_text_field: 1,
            }
            async for bt in bible_texts.find(bt_query, projection):
                key = (bt["book_code"], bt["chapter"], bt["verse"])
                text_map[key] = bt.get(loc_text_field, "") or ""

        # Build result: per phrase, trim to max_locations_per_phrase in
        # canonical order, drop phrases whose post-trim locations list is
        # empty. Returning a recurring phrase with zero examples wastes the
        # AI's tokens and offers no actionable signal.
        result_phrases: list[dict[str, Any]] = []
        for doc in phrase_docs:
            phrase = doc["phrase"]
            enriched: list[dict[str, Any]] = []
            for loc in per_phrase_candidates.get(phrase, []):
                key = (loc["book_code"], loc["chapter"], loc["verse"])
                if key not in text_map:
                    continue
                enriched.append({
                    "book_code": loc["book_code"],
                    "chapter": loc["chapter"],
                    "verse": loc["verse"],
                    "text": text_map[key],
                })
                if len(enriched) >= max_locations_per_phrase:
                    break

            if not enriched:
                continue

            result_phrases.append({
                "phrase": phrase,
                "df": doc["df"],
                "min_word_df": doc["min_word_df"],
                "n": doc["n"],
                "locations": enriched,
            })

        # Order by min_word_df asc, df desc. Python's sort is stable, so a
        # single key tuple gives a stable tie-break.
        result_phrases.sort(key=lambda p: (p["min_word_df"], -p["df"]))

        return {
            "phrase_language": language_code,
            "location_text_language": location_text_language,
            "self_ref": _self_ref_dict(book_code, chapter, verse),
            "phrases": result_phrases,
        }

    except ToolError as e:
        return error_response(e)


def _self_ref_dict(
    book_code: str | None,
    chapter: int | None,
    verse: int | None,
) -> dict[str, Any] | None:
    if book_code is None or chapter is None or verse is None:
        return None
    return {"book_code": book_code, "chapter": chapter, "verse": verse}
