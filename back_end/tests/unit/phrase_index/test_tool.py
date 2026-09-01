"""
Tests for mcp_server/tools/phrase_index.py — get_phrase_context.

Run with: pytest tests/unit/phrase_index/test_tool.py -v
"""

from datetime import datetime, timezone

import pytest

from mcp_server.tools.phrase_index import (
    get_phrase_context,
    MAX_TEXT_CHARS,
    MAX_UNIQUE_4GRAMS,
    MAX_LANGUAGE_CODE_LEN,
)

from .conftest import MockDB


def _seed_languages(db):
    db.seed("languages", [
        {"language_code": "english", "language_name": "English", "is_base_language": True},
        {"language_code": "bughotu", "language_name": "Bughotu", "is_base_language": False},
    ])


def _phrase_doc(lang, phrase, df, min_word_df, locations):
    return {
        "language_code": lang,
        "phrase": phrase,
        "n": 4,
        "df": df,
        "min_word_df": min_word_df,
        "locations": locations,
        "last_rebuilt": datetime.now(timezone.utc),
    }


def _bt(lang, book, chapter, verse, text, *, verified=None, base=False):
    d = {
        "language_code": lang,
        "book_code": book,
        "chapter": chapter,
        "verse": verse,
    }
    if base:
        d["english_text"] = text
    else:
        d["translated_text"] = text
        if verified is not None:
            d["human_verified"] = verified
    return d


@pytest.mark.asyncio
async def test_cross_lingual_mode_returns_verified_target_text():
    """
    Cross-lingual: pass English text with location_text_language=bughotu,
    receive English phrases with only verified Bughotu text at locations.
    """
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("english", "the tent of meeting", df=3, min_word_df=50, locations=[
            {"book_code": "exodus", "chapter": 27, "verse": 21},
            {"book_code": "numbers", "chapter": 1, "verse": 1},
            {"book_code": "numbers", "chapter": 2, "verse": 2},
        ]),
    ])
    db.seed("bible_texts", [
        _bt("bughotu", "exodus", 27, 21, "buq-tent-meeting-1", verified=True),
        _bt("bughotu", "numbers", 1, 1, "buq-tent-meeting-2", verified=True),
        # Unverified — must be excluded
        _bt("bughotu", "numbers", 2, 2, "unverified-draft", verified=False),
    ])

    result = await get_phrase_context(
        db,
        language_code="english",
        text="the tent of meeting was set up in the wilderness",
        location_text_language="bughotu",
    )

    assert result["phrase_language"] == "english"
    assert result["location_text_language"] == "bughotu"
    assert len(result["phrases"]) == 1
    p = result["phrases"][0]
    assert p["phrase"] == "the tent of meeting"
    texts = [loc["text"] for loc in p["locations"]]
    assert "buq-tent-meeting-1" in texts
    assert "buq-tent-meeting-2" in texts
    assert "unverified-draft" not in texts


@pytest.mark.asyncio
async def test_intra_target_mode_default_location_language():
    """
    Intra-target: language_code=bughotu, default location_text_language →
    returns target phrases with verified target text.
    """
    db = MockDB()
    _seed_languages(db)
    # A Bughotu 4-gram present in the draft AND indexed in Bughotu phrase_index.
    db.seed("phrase_index", [
        _phrase_doc("bughotu", "na tent na meeting", df=2, min_word_df=30, locations=[
            {"book_code": "exodus", "chapter": 27, "verse": 21},
        ]),
    ])
    db.seed("bible_texts", [
        _bt("bughotu", "exodus", 27, 21, "buq-verified-text", verified=True),
    ])

    result = await get_phrase_context(
        db,
        language_code="bughotu",
        text="na tent na meeting extra tokens",
    )
    assert result["location_text_language"] == "bughotu"
    assert len(result["phrases"]) == 1
    assert result["phrases"][0]["locations"][0]["text"] == "buq-verified-text"


@pytest.mark.asyncio
async def test_self_reference_excluded():
    """
    (book_code, chapter, verse) tuple is excluded from returned locations.
    """
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("english", "a b c d", df=3, min_word_df=10, locations=[
            {"book_code": "leviticus", "chapter": 1, "verse": 1},  # self-ref
            {"book_code": "leviticus", "chapter": 2, "verse": 1},
        ]),
    ])
    db.seed("bible_texts", [
        _bt("english", "leviticus", 1, 1, "self-ref-text", base=True),
        _bt("english", "leviticus", 2, 1, "other-text", base=True),
    ])

    result = await get_phrase_context(
        db, language_code="english", text="a b c d filler",
        book_code="leviticus", chapter=1, verse=1,
    )
    locs = result["phrases"][0]["locations"]
    keys = [(l["book_code"], l["chapter"], l["verse"]) for l in locs]
    assert ("leviticus", 1, 1) not in keys
    assert ("leviticus", 2, 1) in keys


@pytest.mark.asyncio
async def test_partial_self_ref_raises_tool_error():
    """Partial self-ref (book_code without chapter) is rejected."""
    db = MockDB()
    _seed_languages(db)
    result = await get_phrase_context(
        db, language_code="english", text="a b c d",
        book_code="leviticus",  # chapter/verse missing
    )
    assert "error" in result
    assert result["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_uppercase_language_code_normalized():
    """
    Uppercase language_code returns the same result as lowercase — normalizes
    after validate_language.
    """
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("bughotu", "na na na na", df=2, min_word_df=5, locations=[
            {"book_code": "genesis", "chapter": 1, "verse": 1},
        ]),
    ])
    db.seed("bible_texts", [
        _bt("bughotu", "genesis", 1, 1, "buq-text", verified=True),
    ])

    upper = await get_phrase_context(db, "Bughotu", "na na na na extra")
    lower = await get_phrase_context(db, "bughotu", "na na na na extra")
    assert upper == lower
    assert upper["phrase_language"] == "bughotu"


@pytest.mark.asyncio
async def test_unverified_included_for_base_language():
    """
    location_text_language=english (base): no human_verified filter.
    """
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("english", "a b c d", df=1, min_word_df=10, locations=[
            {"book_code": "genesis", "chapter": 1, "verse": 1},
        ]),
    ])
    # English base — no human_verified field.
    db.seed("bible_texts", [
        _bt("english", "genesis", 1, 1, "english-text", base=True),
    ])

    result = await get_phrase_context(db, "english", "a b c d filler")
    assert result["phrases"][0]["locations"][0]["text"] == "english-text"


@pytest.mark.asyncio
async def test_min_word_df_max_filter_honored():
    """Phrases above min_word_df_max are filtered out."""
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("english", "a b c d", df=2, min_word_df=50, locations=[
            {"book_code": "genesis", "chapter": 1, "verse": 1},
        ]),
        _phrase_doc("english", "e f g h", df=2, min_word_df=500, locations=[
            {"book_code": "genesis", "chapter": 1, "verse": 2},
        ]),
    ])
    db.seed("bible_texts", [
        _bt("english", "genesis", 1, 1, "kept", base=True),
        _bt("english", "genesis", 1, 2, "filtered", base=True),
    ])

    result = await get_phrase_context(
        db, "english", "a b c d e f g h filler", min_word_df_max=200,
    )
    phrases = [p["phrase"] for p in result["phrases"]]
    assert "a b c d" in phrases
    assert "e f g h" not in phrases


@pytest.mark.asyncio
async def test_max_locations_per_phrase_cap_honored():
    """Locations are trimmed to max_locations_per_phrase."""
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("english", "a b c d", df=5, min_word_df=10, locations=[
            {"book_code": "genesis", "chapter": 1, "verse": i} for i in range(1, 6)
        ]),
    ])
    db.seed("bible_texts", [
        _bt("english", "genesis", 1, i, f"text-{i}", base=True) for i in range(1, 6)
    ])

    result = await get_phrase_context(
        db, "english", "a b c d filler", max_locations_per_phrase=2,
    )
    assert len(result["phrases"][0]["locations"]) == 2


@pytest.mark.asyncio
async def test_phrase_ordering_by_min_word_df_asc_then_df_desc():
    """Ordered by min_word_df ascending, df descending as tie-break."""
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("english", "p1 x x x", df=3, min_word_df=100,
                    locations=[{"book_code": "genesis", "chapter": 1, "verse": 1}]),
        _phrase_doc("english", "p2 y y y", df=5, min_word_df=50,
                    locations=[{"book_code": "genesis", "chapter": 1, "verse": 2}]),
        _phrase_doc("english", "p3 z z z", df=10, min_word_df=50,
                    locations=[{"book_code": "genesis", "chapter": 1, "verse": 3}]),
    ])
    db.seed("bible_texts", [
        _bt("english", "genesis", 1, i, f"t{i}", base=True) for i in range(1, 4)
    ])

    result = await get_phrase_context(
        db, "english", "p1 x x x p2 y y y p3 z z z filler",
    )
    phrases = [p["phrase"] for p in result["phrases"]]
    # min_word_df=50 group first, tie-broken by df desc (10 > 5), then 100.
    assert phrases == ["p3 z z z", "p2 y y y", "p1 x x x"]


@pytest.mark.asyncio
async def test_empty_locations_phrase_dropped():
    """
    Recurring phrase with zero verified renderings in location_text_language
    is DROPPED from the result — never returned with empty locations.
    """
    db = MockDB()
    _seed_languages(db)
    db.seed("phrase_index", [
        _phrase_doc("english", "a b c d", df=2, min_word_df=10, locations=[
            {"book_code": "genesis", "chapter": 1, "verse": 1},
        ]),
    ])
    db.seed("bible_texts", [
        # Only unverified target text exists → verified-only filter drops it.
        _bt("bughotu", "genesis", 1, 1, "unverified", verified=False),
    ])

    result = await get_phrase_context(
        db, "english", "a b c d filler", location_text_language="bughotu",
    )
    assert result["phrases"] == []


@pytest.mark.asyncio
async def test_empty_text_returns_empty_phrases_no_error():
    """Empty/short text → phrases: [], no error."""
    db = MockDB()
    _seed_languages(db)
    result = await get_phrase_context(db, "english", "")
    assert result["phrases"] == []
    assert "error" not in result


@pytest.mark.asyncio
async def test_text_exceeding_max_chars_raises():
    """Text over MAX_TEXT_CHARS → ToolError; no Mongo round-trip."""
    db = MockDB()
    _seed_languages(db)
    huge = "x " * ((MAX_TEXT_CHARS // 2) + 100)  # comfortably over
    assert len(huge) > MAX_TEXT_CHARS
    result = await get_phrase_context(db, "english", huge)
    assert "error" in result
    assert result["error"]["code"] == "invalid_input"
    # Confirm no phrase_index lookup happened.
    assert "phrase_index" not in db.collections


@pytest.mark.asyncio
async def test_unique_4gram_count_exceeds_max_raises():
    """Unique 4-gram count over MAX_UNIQUE_4GRAMS → ToolError."""
    db = MockDB()
    _seed_languages(db)
    # Build a text with distinct tokens so each 4-gram is unique.
    # For >MAX_UNIQUE_4GRAMS unique 4-grams, need >MAX_UNIQUE_4GRAMS + 3 tokens.
    n_tokens = MAX_UNIQUE_4GRAMS + 10
    tokens = [f"t{i}" for i in range(n_tokens)]
    text = " ".join(tokens)
    # But cap by MAX_TEXT_CHARS.
    if len(text) > MAX_TEXT_CHARS:
        pytest.skip("Cannot construct case within MAX_TEXT_CHARS")
    result = await get_phrase_context(db, "english", text)
    assert "error" in result
    assert result["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_over_long_language_code_raises():
    """language_code longer than MAX_LANGUAGE_CODE_LEN → ToolError."""
    db = MockDB()
    _seed_languages(db)
    long_code = "x" * (MAX_LANGUAGE_CODE_LEN + 1)
    result = await get_phrase_context(db, long_code, "a b c d filler")
    assert "error" in result
    assert result["error"]["code"] == "invalid_input"
