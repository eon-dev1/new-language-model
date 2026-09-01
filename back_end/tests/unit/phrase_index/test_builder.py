"""
Tests for utils/phrase_index/builder.py — invariants from source plan §4.1.

Run with: pytest tests/unit/phrase_index/test_builder.py -v
"""

from datetime import datetime, timezone

import pytest

from utils.phrase_index.builder import (
    build_phrase_index,
    MAX_LOCATIONS,
    N_PHRASE,
    PHRASE_MIN_DF,
)

from .conftest import MockDB


def _verse(lang, book, chapter, verse, text, *, human_verified=None, is_english=False):
    d = {
        "language_code": lang,
        "book_code": book,
        "chapter": chapter,
        "verse": verse,
    }
    if is_english:
        d["english_text"] = text
    else:
        d["translated_text"] = text
        if human_verified is not None:
            d["human_verified"] = human_verified
    return d


def _seed(db, language, is_base, verses):
    db.seed("languages", [{"language_code": language, "is_base_language": is_base}])
    db.seed("bible_texts", verses)


@pytest.mark.asyncio
async def test_p1_every_doc_df_ge_min():
    """P1: every emitted doc has df >= PHRASE_MIN_DF (= 2)."""
    db = MockDB()
    # Two verses each with the same 4-gram — df=2. And unique 4-grams in
    # each verse must NOT be emitted (df=1).
    v1 = "the quick brown fox jumps over the lazy dog"
    v2 = "why did the quick brown fox eat a large pizza"
    _seed(db, "english", True, [
        _verse("english", "genesis", 1, 1, v1, is_english=True),
        _verse("english", "genesis", 1, 2, v2, is_english=True),
    ])

    result = await build_phrase_index(db, "english")

    emitted = db.get_collection("phrase_index").docs
    assert result["phrases_emitted"] == len(emitted) > 0
    for doc in emitted:
        assert doc["df"] >= PHRASE_MIN_DF


@pytest.mark.asyncio
async def test_p2_locations_length_and_no_dup_verses():
    """P2: len(locations) == min(df, MAX_LOCATIONS); no dup verse refs."""
    db = MockDB()
    # Phrase "a b c d" in 3 distinct verses.
    _seed(db, "english", True, [
        _verse("english", "genesis", 1, i, "a b c d e", is_english=True)
        for i in range(1, 4)
    ])

    await build_phrase_index(db, "english")
    emitted = db.get_collection("phrase_index").docs

    for doc in emitted:
        assert len(doc["locations"]) == min(doc["df"], MAX_LOCATIONS)
        # No duplicate verse refs in locations
        seen = set()
        for loc in doc["locations"]:
            key = (loc["book_code"], loc["chapter"], loc["verse"])
            assert key not in seen
            seen.add(key)


@pytest.mark.asyncio
async def test_p2b_df_exact_past_cap():
    """
    P2b (load-bearing): df counter is exact past MAX_LOCATIONS. This test
    naked-catches the F-BUG-1 reconciliation. P2 alone passes vacuously
    under the buggy df = len(locations) impl (1000 == min(1000, 1000)).
    """
    # Use small MAX_LOCATIONS to keep the test fast.
    import utils.phrase_index.builder as builder_mod

    original_max = builder_mod.MAX_LOCATIONS
    builder_mod.MAX_LOCATIONS = 5  # small cap
    try:
        db = MockDB()
        # Same 4-gram in 7 distinct verses; cap is 5.
        _seed(db, "english", True, [
            _verse("english", "genesis", 1, i, "a b c d filler", is_english=True)
            for i in range(1, 8)
        ])

        await build_phrase_index(db, "english")
        emitted = db.get_collection("phrase_index").docs

        # Find the "a b c d" phrase — it's the only 4-gram that recurs
        # 7 times (each of the other 4-grams differs by position).
        target = next(d for d in emitted if d["phrase"] == "a b c d")
        assert target["df"] == 7, f"df should be 7 (exact past cap), got {target['df']}"
        assert len(target["locations"]) == 5
    finally:
        builder_mod.MAX_LOCATIONS = original_max


@pytest.mark.asyncio
async def test_p4_no_df_cap():
    """P4: no DF_CAP truncation — high-df phrases are kept."""
    db = MockDB()
    # 50 verses with the same 4-gram → df=50 emitted, not capped.
    _seed(db, "english", True, [
        _verse("english", "genesis", 1, i, "x y z w extra", is_english=True)
        for i in range(1, 51)
    ])

    await build_phrase_index(db, "english")
    emitted = db.get_collection("phrase_index").docs
    max_df = max(d["df"] for d in emitted)
    assert max_df == 50


@pytest.mark.asyncio
async def test_p5_min_word_df_semantics():
    """
    P5 (both halves):
        min_word_df == min(word_df[t] for t in tokens(phrase))
        min_word_df >= df
    """
    db = MockDB()
    # "the tent of meeting" recurs; "tent" and "meeting" are rare, "the" and
    # "of" are common. min_word_df should equal the rarest token's word_df.
    _seed(db, "english", True, [
        _verse("english", "genesis", 1, 1, "the tent of meeting was set up", is_english=True),
        _verse("english", "genesis", 1, 2, "and the tent of meeting stood there", is_english=True),
        _verse("english", "genesis", 1, 3, "the ark of the covenant", is_english=True),
    ])

    await build_phrase_index(db, "english")
    emitted = db.get_collection("phrase_index").docs
    tent = next(d for d in emitted if d["phrase"] == "the tent of meeting")

    # Words present in each verse:
    #   v1: the, tent, of, meeting, was, set, up
    #   v2: and, the, tent, of, meeting, stood, there
    #   v3: the, ark, of, the, covenant
    # word_df: the=3, of=3, tent=2, meeting=2
    # min_word_df("the tent of meeting") = min(3, 2, 3, 2) = 2
    assert tent["min_word_df"] == 2
    assert tent["min_word_df"] >= tent["df"]  # df=2 as well


@pytest.mark.asyncio
async def test_determinism_across_runs():
    """
    Two runs with identical input produce identical output when sorted by
    (language_code, phrase) and last_rebuilt is projected out. Insertion
    order isn't preserved by Mongo under a unique index; the sort makes the
    comparison meaningful.
    """
    def make_db():
        db = MockDB()
        _seed(db, "english", True, [
            _verse("english", "genesis", 1, i, "a b c d e f g", is_english=True)
            for i in range(1, 4)
        ])
        return db

    db1, db2 = make_db(), make_db()
    await build_phrase_index(db1, "english")
    await build_phrase_index(db2, "english")

    def normalize(coll):
        docs = list(coll.docs)
        docs.sort(key=lambda d: (d["language_code"], d["phrase"]))
        for d in docs:
            d.pop("last_rebuilt", None)
        return docs

    assert normalize(db1.get_collection("phrase_index")) == normalize(
        db2.get_collection("phrase_index")
    )


@pytest.mark.asyncio
async def test_idempotent_delete_only_target_language():
    """Rebuild deletes only target language_code; foreign-lang rows survive."""
    db = MockDB()
    # Pre-seed phrase_index with foreign-language rows.
    db.seed("phrase_index", [
        {"language_code": "french", "phrase": "le tent", "n": 2, "df": 5,
         "min_word_df": 10, "locations": [], "last_rebuilt": datetime.now(timezone.utc)},
    ])
    _seed(db, "english", True, [
        _verse("english", "genesis", 1, 1, "a b c d e", is_english=True),
        _verse("english", "genesis", 1, 2, "a b c d f", is_english=True),
    ])

    await build_phrase_index(db, "english")
    remaining = db.get_collection("phrase_index").docs
    assert any(d["language_code"] == "french" for d in remaining)


@pytest.mark.asyncio
async def test_no_short_verse_docs():
    """
    Verses with < 4 tokens contribute no docs. Every emitted doc has n == 4.
    """
    db = MockDB()
    _seed(db, "english", True, [
        _verse("english", "genesis", 1, 1, "jesus wept", is_english=True),  # 2 tokens
        _verse("english", "genesis", 1, 2, "jesus wept", is_english=True),
        _verse("english", "genesis", 1, 3, "a b c d recurring", is_english=True),
        _verse("english", "genesis", 1, 4, "a b c d recurring", is_english=True),
    ])

    await build_phrase_index(db, "english")
    emitted = db.get_collection("phrase_index").docs
    assert all(d["n"] == N_PHRASE for d in emitted)
    # "jesus wept" is only 2 tokens — no doc from those verses.
    assert not any(d["phrase"] == "jesus wept" for d in emitted)


@pytest.mark.asyncio
async def test_intra_verse_repeat_dedup():
    """
    Same 4-gram twice within one verse counts df once and appears in
    locations once.
    """
    db = MockDB()
    # "a b c d" appears twice in verse 1 (5-token overlap), then once in verse 2.
    # Actually, to appear twice within a single verse: "a b c d x a b c d" —
    # 4-grams starting at pos 0 and pos 5.
    _seed(db, "english", True, [
        _verse("english", "genesis", 1, 1, "a b c d x a b c d", is_english=True),
        _verse("english", "genesis", 1, 2, "a b c d ending", is_english=True),
    ])

    await build_phrase_index(db, "english")
    emitted = db.get_collection("phrase_index").docs
    target = next(d for d in emitted if d["phrase"] == "a b c d")
    # 2 distinct verses, despite twice-in-verse-1.
    assert target["df"] == 2
    keys = [(l["book_code"], l["chapter"], l["verse"]) for l in target["locations"]]
    assert keys == [("genesis", 1, 1), ("genesis", 1, 2)]


@pytest.mark.asyncio
async def test_verified_only_filter_non_base():
    """
    Target-language build: unverified verses do not contribute.
    English build: all verses contribute (no human_verified filter).
    """
    db = MockDB()
    _seed(db, "bughotu", False, [
        _verse("bughotu", "genesis", 1, 1, "a b c d recurring", human_verified=True),
        _verse("bughotu", "genesis", 1, 2, "a b c d recurring", human_verified=True),
        # Unverified recurring — must NOT contribute.
        _verse("bughotu", "genesis", 1, 3, "x y z w unverified", human_verified=False),
        _verse("bughotu", "genesis", 1, 4, "x y z w unverified", human_verified=False),
    ])

    await build_phrase_index(db, "bughotu")
    emitted = db.get_collection("phrase_index").docs
    phrases = {d["phrase"] for d in emitted}
    assert "a b c d" in phrases
    assert "x y z w" not in phrases  # unverified pair should be filtered


@pytest.mark.asyncio
async def test_empty_build_guard_no_insert_many_call():
    """
    Verified-only target build with zero verified verses: no insert_many
    call, no crash, returns phrases_emitted=0.
    """
    db = MockDB()
    _seed(db, "bughotu", False, [
        _verse("bughotu", "genesis", 1, 1, "a b c d e", human_verified=False),
        _verse("bughotu", "genesis", 1, 2, "a b c d f", human_verified=False),
    ])

    result = await build_phrase_index(db, "bughotu")
    assert result["phrases_emitted"] == 0
    # MockCollection.insert_many raises on []; if we called it, this would
    # have raised. Also assert the call list is empty.
    assert db.get_collection("phrase_index").insert_many_calls == []
