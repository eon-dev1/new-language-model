# tests/test_export_bible.py
"""Pure function tests for USFM export logic.

No MongoDB, no async, no fixtures required.
Tests _build_usfm_content and _BOOK_EXPORT_MAP directly.
"""

import pytest
from routes.export_bible import _build_usfm_content, _BOOK_EXPORT_MAP


# ---------------------------------------------------------------------------
# Module-level verse fixtures — reused across test cases
# ---------------------------------------------------------------------------

SAMPLE_VERSES = [
    {"chapter": 1, "verse": 1, "translated_text": "Dispela em i tok"},
    {"chapter": 1, "verse": 2, "translated_text": "Abraham em i papa"},
    {"chapter": 2, "verse": 1, "translated_text": "Jisas i bon"},
]

EMPTY_VERSES = [
    {"chapter": 1, "verse": 1, "translated_text": None},
    {"chapter": 1, "verse": 2, "translated_text": ""},
]

MIXED_VERSES = [
    {"chapter": 1, "verse": 1, "translated_text": None},
    {"chapter": 1, "verse": 2, "translated_text": "Some text"},
    {"chapter": 2, "verse": 1, "translated_text": None},
    {"chapter": 3, "verse": 1, "translated_text": "More text"},
]


# ---------------------------------------------------------------------------
# Test 1 — \toc3 uses USFM 3-letter code, not display name
# ---------------------------------------------------------------------------

class TestToc3IsUsfmCode:
    """\\toc3 must be the USFM code (e.g. MAT), not the English display name."""

    def test_toc3_is_usfm_code_not_display_name(self):
        lines = _build_usfm_content("matthew", SAMPLE_VERSES, "MATYU", "Tok Pisin")
        toc3_lines = [l for l in lines if l.startswith("\\toc3 ")]
        assert len(toc3_lines) == 1
        assert toc3_lines[0] == "\\toc3 MAT"

    def test_toc3_does_not_contain_display_name(self):
        lines = _build_usfm_content("matthew", SAMPLE_VERSES, "MATYU", "Tok Pisin")
        assert "\\toc3 Matthew" not in lines


# ---------------------------------------------------------------------------
# Test 2 — Filename zero-padding via canonical order in _BOOK_EXPORT_MAP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("book_code,expected_order", [
    ("genesis", 1),
    ("matthew", 40),
    ("revelation", 66),
    ("1_enoch", 67),
])
def test_canonical_orders(book_code, expected_order):
    _, _, order = _BOOK_EXPORT_MAP[book_code]
    assert order == expected_order


# ---------------------------------------------------------------------------
# Test 3 — Unknown book_code is not in map (safe to skip)
# ---------------------------------------------------------------------------

class TestUnknownBookCode:
    """Unknown book codes must not exist in _BOOK_EXPORT_MAP."""

    def test_unknown_returns_empty_list(self):
        result = _build_usfm_content("jubilees", SAMPLE_VERSES, "Jubilees", "Tok Pisin")
        assert result == []


# ---------------------------------------------------------------------------
# Test 4 — book_name=None falls back to English display name from map
# ---------------------------------------------------------------------------

class TestBookNameFallback:
    """When book_name is None, fall back to display name from _BOOK_EXPORT_MAP."""

    def test_h_uses_display_name_fallback(self):
        lines = _build_usfm_content("matthew", SAMPLE_VERSES, None, "Tok Pisin")
        assert "\\h Matthew" in lines

    def test_toc1_uses_display_name_fallback(self):
        lines = _build_usfm_content("matthew", SAMPLE_VERSES, None, "Tok Pisin")
        assert "\\toc1 Matthew" in lines


# ---------------------------------------------------------------------------
# Test 5 — Verses with null/empty translated_text are skipped
# ---------------------------------------------------------------------------

class TestNullVerseSkipped:
    """Verses with None or empty translated_text must not appear in output."""

    def test_no_v_lines_for_empty_verses(self):
        lines = _build_usfm_content("matthew", EMPTY_VERSES, "MATYU", "Tok Pisin")
        assert not any(l.startswith("\\v ") for l in lines)

    def test_none_not_rendered_as_v_none(self):
        lines = _build_usfm_content("matthew", EMPTY_VERSES, "MATYU", "Tok Pisin")
        assert not any("None" in l for l in lines)


# ---------------------------------------------------------------------------
# Test 6 — Lazy \c/\p emission: only emit before first non-empty verse in chapter
# ---------------------------------------------------------------------------

class TestLazyChapterEmission:
    """Chapter markers must be emitted lazily — only when a non-empty verse follows."""

    def test_chapter_with_text_emits_c_marker(self):
        lines = _build_usfm_content("matthew", MIXED_VERSES, "MATYU", "Tok Pisin")
        assert "\\c 1" in lines   # chapter 1 has verse 2 with text

    def test_chapter_all_null_does_not_emit_c_marker(self):
        lines = _build_usfm_content("matthew", MIXED_VERSES, "MATYU", "Tok Pisin")
        assert "\\c 2" not in lines   # chapter 2 has only null text

    def test_later_chapter_with_text_emits_c_marker(self):
        lines = _build_usfm_content("matthew", MIXED_VERSES, "MATYU", "Tok Pisin")
        assert "\\c 3" in lines   # chapter 3 has text

    def test_p_marker_follows_c_marker(self):
        lines = _build_usfm_content("matthew", MIXED_VERSES, "MATYU", "Tok Pisin")
        c1_idx = lines.index("\\c 1")
        assert lines[c1_idx + 1] == "\\p"


# ---------------------------------------------------------------------------
# Test 7 — All-empty book produces only headers (no \v or \c lines)
# ---------------------------------------------------------------------------

class TestAllEmptyBookHeadersOnly:
    """A book with all null/empty verses must produce only header lines."""

    def test_id_line_present(self):
        lines = _build_usfm_content("matthew", EMPTY_VERSES, "MATYU", "Tok Pisin")
        assert any(l.startswith("\\id ") for l in lines)

    def test_no_v_lines(self):
        lines = _build_usfm_content("matthew", EMPTY_VERSES, "MATYU", "Tok Pisin")
        assert not any(l.startswith("\\v ") for l in lines)

    def test_no_c_lines(self):
        lines = _build_usfm_content("matthew", EMPTY_VERSES, "MATYU", "Tok Pisin")
        assert not any(l.startswith("\\c ") for l in lines)

    def test_no_p_lines(self):
        lines = _build_usfm_content("matthew", EMPTY_VERSES, "MATYU", "Tok Pisin")
        assert "\\p" not in lines
