# tests/test_usfm_book_codes.py
"""Tests for USFM book code mapping functionality."""

import pytest
from utils.usfm_parser.usfm_book_codes import (
    USFM_BOOK_DATA,
    USFM_TO_BOOK_CODE,
    USFM_TO_BOOK_NAME,
    BOOK_CODE_TO_USFM,
    usfm_code_to_book_code,
    usfm_code_to_book_name,
    book_code_to_usfm_code,
    book_name_to_book_code,
    is_valid_usfm_code,
    get_all_usfm_codes,
    get_all_book_codes,
)


class TestUSFMBookCodeMappings:
    """Test the USFM book code mapping dictionaries."""

    def test_usfm_book_data_has_66_books(self):
        """The Bible has 66 books."""
        assert len(USFM_BOOK_DATA) == 66

    def test_usfm_to_book_code_has_66_entries(self):
        assert len(USFM_TO_BOOK_CODE) == 66

    def test_usfm_to_book_name_has_66_entries(self):
        assert len(USFM_TO_BOOK_NAME) == 66

    def test_book_code_to_usfm_has_66_entries(self):
        assert len(BOOK_CODE_TO_USFM) == 66

    def test_all_book_codes_are_lowercase(self):
        """MongoDB book codes should be lowercase."""
        for book_code in USFM_TO_BOOK_CODE.values():
            assert book_code == book_code.lower()
            assert book_code.isidentifier() or book_code[0].isdigit()

    def test_all_usfm_codes_are_uppercase(self):
        """USFM codes should be uppercase."""
        for usfm_code in USFM_BOOK_DATA.keys():
            assert usfm_code == usfm_code.upper()


class TestUSFMCodeToBookCode:
    """Test usfm_code_to_book_code function."""

    @pytest.mark.parametrize("usfm_code,expected", [
        ("GEN", "genesis"),
        ("EXO", "exodus"),
        ("LEV", "leviticus"),
        ("NUM", "numbers"),
        ("DEU", "deuteronomy"),
        ("1SA", "1_samuel"),
        ("2SA", "2_samuel"),
        ("1KI", "1_kings"),
        ("2KI", "2_kings"),
        ("1CH", "1_chronicles"),
        ("2CH", "2_chronicles"),
        ("PSA", "psalms"),
        ("SNG", "song_of_solomon"),
        ("MAT", "matthew"),
        ("MRK", "mark"),
        ("LUK", "luke"),
        ("JHN", "john"),
        ("ACT", "acts"),
        ("ROM", "romans"),
        ("1CO", "1_corinthians"),
        ("2CO", "2_corinthians"),
        ("REV", "revelation"),
    ])
    def test_valid_usfm_codes(self, usfm_code, expected):
        """Test conversion of valid USFM codes."""
        assert usfm_code_to_book_code(usfm_code) == expected

    def test_case_insensitive(self):
        """USFM codes should be case-insensitive."""
        assert usfm_code_to_book_code("gen") == "genesis"
        assert usfm_code_to_book_code("Gen") == "genesis"
        assert usfm_code_to_book_code("GEN") == "genesis"

    def test_invalid_code_returns_none(self):
        """Invalid USFM codes should return None."""
        assert usfm_code_to_book_code("XXX") is None
        assert usfm_code_to_book_code("INVALID") is None
        assert usfm_code_to_book_code("") is None


class TestUSFMCodeToBookName:
    """Test usfm_code_to_book_name function."""

    @pytest.mark.parametrize("usfm_code,expected", [
        ("GEN", "Genesis"),
        ("1SA", "1 Samuel"),
        ("2KI", "2 Kings"),
        ("SNG", "Song of Solomon"),
        ("MAT", "Matthew"),
        ("1CO", "1 Corinthians"),
        ("REV", "Revelation"),
    ])
    def test_valid_usfm_codes(self, usfm_code, expected):
        """Test conversion to display names."""
        assert usfm_code_to_book_name(usfm_code) == expected

    def test_invalid_code_returns_none(self):
        """Invalid codes should return None."""
        assert usfm_code_to_book_name("XXX") is None


class TestBookCodeToUSFM:
    """Test book_code_to_usfm_code function."""

    @pytest.mark.parametrize("book_code,expected", [
        ("genesis", "GEN"),
        ("exodus", "EXO"),
        ("1_samuel", "1SA"),
        ("song_of_solomon", "SNG"),
        ("matthew", "MAT"),
        ("revelation", "REV"),
    ])
    def test_reverse_mapping(self, book_code, expected):
        """Test reverse mapping from book_code to USFM."""
        assert book_code_to_usfm_code(book_code) == expected

    def test_invalid_book_code_returns_none(self):
        """Invalid book codes should return None."""
        assert book_code_to_usfm_code("invalid") is None
        assert book_code_to_usfm_code("not_a_book") is None
        assert book_code_to_usfm_code("gen_esis") is None  # Misspelled

    def test_case_insensitive(self):
        """Book code lookup should be case-insensitive."""
        assert book_code_to_usfm_code("genesis") == "GEN"
        assert book_code_to_usfm_code("Genesis") == "GEN"
        assert book_code_to_usfm_code("GENESIS") == "GEN"


class TestBookNameToBookCode:
    """Test book_name_to_book_code function."""

    @pytest.mark.parametrize("book_name,expected", [
        ("Genesis", "genesis"),
        ("1 Samuel", "1_samuel"),
        ("Song of Solomon", "song_of_solomon"),
        ("Matthew", "matthew"),
    ])
    def test_name_to_code(self, book_name, expected):
        """Test conversion from display name to book code."""
        assert book_name_to_book_code(book_name) == expected

    def test_invalid_name_returns_none(self):
        """Invalid book names should return None."""
        assert book_name_to_book_code("Invalid Book") is None


class TestIsValidUSFMCode:
    """Test is_valid_usfm_code function."""

    def test_valid_codes(self):
        """Test that all known codes are valid."""
        assert is_valid_usfm_code("GEN")
        assert is_valid_usfm_code("MAT")
        assert is_valid_usfm_code("REV")
        assert is_valid_usfm_code("1SA")

    def test_case_insensitive(self):
        """Validation should be case-insensitive."""
        assert is_valid_usfm_code("gen")
        assert is_valid_usfm_code("Gen")

    def test_invalid_codes(self):
        """Invalid codes should return False."""
        assert not is_valid_usfm_code("XXX")
        assert not is_valid_usfm_code("")
        assert not is_valid_usfm_code("GENESIS")


class TestGetAllCodes:
    """Test get_all_* functions."""

    def test_get_all_usfm_codes(self):
        """Should return all 66 USFM codes."""
        codes = get_all_usfm_codes()
        assert len(codes) == 66
        assert "GEN" in codes
        assert "REV" in codes
        assert codes[0] == "GEN"  # First book
        assert codes[-1] == "REV"  # Last book

    def test_get_all_book_codes(self):
        """Should return all 66 book codes."""
        codes = get_all_book_codes()
        assert len(codes) == 66
        assert "genesis" in codes
        assert "revelation" in codes

    def test_canonical_order_preserved(self):
        """Book order should be canonical (Genesis to Revelation)."""
        usfm_codes = get_all_usfm_codes()
        book_codes = get_all_book_codes()

        # Check order
        assert usfm_codes.index("GEN") < usfm_codes.index("EXO")
        assert usfm_codes.index("MAL") < usfm_codes.index("MAT")  # OT before NT
        assert book_codes.index("genesis") < book_codes.index("matthew")


class TestRoundTripConversions:
    """Test that conversions are reversible."""

    def test_usfm_to_book_code_roundtrip(self):
        """Converting USFM -> book_code -> USFM should give original."""
        for usfm_code in get_all_usfm_codes():
            book_code = usfm_code_to_book_code(usfm_code)
            back_to_usfm = book_code_to_usfm_code(book_code)
            assert back_to_usfm == usfm_code

    def test_all_mappings_consistent(self):
        """All mapping dictionaries should be consistent."""
        for usfm_code, (book_code, book_name) in USFM_BOOK_DATA.items():
            assert USFM_TO_BOOK_CODE[usfm_code] == book_code
            assert USFM_TO_BOOK_NAME[usfm_code] == book_name
            assert BOOK_CODE_TO_USFM[book_code] == usfm_code