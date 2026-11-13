# tests/unit/shared/test_storage_conventions.py
"""
Tests for the canonical stored forms in shared/storage_conventions.py.

Each test's docstring names the implementation change that must make it fail.
"""

import re
import unicodedata
from datetime import datetime, timedelta, timezone

import pytest

from shared.storage_conventions import (
    fold_for_search,
    normalize_word,
    to_utc_iso,
    utc_now_iso,
)
from utils.word_index.tokenizer import tokenize_verse


# Every input where a case operation followed by NFC can behave unexpectedly
# has the shape (cased character [+ combining mark]). Exhaustive over all
# code points with a case mapping, alone and followed by each of these marks:
# acute, diaeresis, iota subscript, psili, grave, perispomeni.
_COMBINING_MARKS = ("\u0301", "\u0308", "\u0345", "\u0313", "\u0300", "\u0342")


def _cased_code_point_inputs() -> list[str]:
    inputs = []
    for code_point in range(0x110000):
        if 0xD800 <= code_point <= 0xDFFF:
            continue
        char = chr(code_point)
        if char.lower() != char or char.casefold() != char:
            inputs.append(char)
            inputs.extend(char + mark for mark in _COMBINING_MARKS)
    return inputs


CASED_INPUTS = _cased_code_point_inputs()


def _nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


class TestNormalizeWord:
    def test_composes_decomposed_input(self):
        """Fails if the NFC step is removed."""
        assert normalize_word("e\u0301") == "\u00e9"

    def test_strips_and_lowercases(self):
        """Fails if strip() or lower() is removed."""
        assert normalize_word("  Tok  ") == "tok"

    def test_lower_not_casefold(self):
        """Fails if lower() becomes casefold() (ß -> ss, final ς -> σ)."""
        assert normalize_word("Straße") == "straße"
        assert normalize_word("ΟΔΥΣ") == "οδυς"

    def test_idempotent(self):
        """Fails if NFC is moved before lower(): lower() can emit non-NFC text."""
        unstable = [
            ascii(text)
            for text in CASED_INPUTS
            if normalize_word(normalize_word(text)) != normalize_word(text)
        ]
        assert unstable == []

    @pytest.mark.parametrize("word", ["T\u0308", "\u03aa\u0301"])
    def test_matches_tokenizer(self, word):
        """Fails if the tokenizer goes back to a bare lower(): these are inputs
        where lower() alone leaves a decomposed sequence."""
        assert normalize_word(word) == tokenize_verse(word)[0]

    def test_blank_returns_empty(self):
        """Documents that blank input is not rejected here; callers reject it."""
        assert normalize_word("   ") == ""


class TestFoldForSearch:
    def test_casefold_not_lower(self):
        """Fails if casefold() becomes lower()."""
        assert fold_for_search("Straße") == "strasse"
        assert fold_for_search("ΑΣ") == fold_for_search("ας") == "ασ"

    def test_nfd_and_nfc_fold_alike(self):
        """Fails if the leading NFC is removed (Greek iota-subscript sequences
        casefold differently in decomposed form)."""
        mismatched = [
            ascii(text)
            for text in CASED_INPUTS
            if fold_for_search(_nfd(text)) != fold_for_search(_nfc(text))
        ]
        assert mismatched == []

    def test_precomposed_term_matches_text(self):
        """Fails if the trailing NFC is removed: casefold() decomposes ΐ, while
        Ϊ + acute folds to the composed form."""
        assert fold_for_search("\u0390") in fold_for_search("\u03aa\u0301")

    def test_idempotent(self):
        """Fails if the trailing NFC is removed."""
        unstable = [
            ascii(text)
            for text in CASED_INPUTS
            if fold_for_search(fold_for_search(text)) != fold_for_search(text)
        ]
        assert unstable == []

    def test_keeps_surrounding_spaces(self):
        """Fails if strip() is added."""
        assert fold_for_search(" A ") == " a "


class TestToUtcIso:
    def test_zero_microseconds_keep_fraction(self):
        """Fails if timespec="microseconds" is dropped."""
        moment = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert to_utc_iso(moment) == "2026-01-01T12:00:00.000000+00:00"

    def test_converts_offset_to_utc(self):
        """Fails if astimezone(timezone.utc) is removed."""
        moment = datetime(2026, 1, 1, 7, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        assert to_utc_iso(moment) == "2026-01-01T12:00:00.000000+00:00"

    def test_naive_raises(self):
        """Fails if the naive check is removed."""
        with pytest.raises(ValueError):
            to_utc_iso(datetime(2026, 1, 1, 12, 0, 0))


class TestUtcNowIso:
    def test_shape_and_value(self):
        """Fails if utc_now_iso stops using to_utc_iso's format or the current time."""
        before = datetime.now(timezone.utc)
        result = utc_now_iso()
        after = datetime.now(timezone.utc)
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}\+00:00", result)
        assert before <= datetime.fromisoformat(result) <= after
