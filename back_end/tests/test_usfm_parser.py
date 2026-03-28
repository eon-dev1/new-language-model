# tests/test_usfm_parser.py
"""Tests for USFM parsing functionality."""

import pytest
from pathlib import Path
import tempfile
import os

from utils.usfm_parser.usfm_parser import (
    ParsedVerse,
    ParseResult,
    parse_usfm_file,
    parse_usfm_directory,
    iter_usfm_verses,
    _extract_book_id,
)


# Sample USFM content for testing
SAMPLE_GENESIS_USFM = r"""\id GEN
\h Genesis
\toc1 Genesis
\mt1 Genesis
\c 1
\s1 The Creation of the World
\p
\v 1 \w In the beginning|strong="H7225"\w* \w God|strong="H0430"\w* \w created|strong="H1254"\w* \w the heavens|strong="H8064"\w* and the \w earth|strong="H0776"\w*.
\v 2 \w Now|strong="H1961"\w* the earth was \w without shape|strong="H8414"\w* and \w empty|strong="H0922"\w*.
\v 3 \w God|strong="H0430"\w* \w said|strong="H0559"\w*, "Let there be light." And there was light!
\c 2
\v 1 The heavens and the earth were completed.
\v 2 By the seventh day God finished the work.
"""

SAMPLE_MATTHEW_USFM = r"""\id MAT
\h Matthew
\mt1 Matthew
\c 1
\v 1 This is the record of the genealogy of Jesus Christ.
\v 2 Abraham was the father of Isaac.
\c 2
\v 1 After Jesus was born in Bethlehem.
"""


@pytest.fixture
def temp_usfm_file():
    """Create a temporary USFM file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.usfm', delete=False, encoding='utf-8') as f:
        f.write(SAMPLE_GENESIS_USFM)
        temp_path = f.name
    yield Path(temp_path)
    os.unlink(temp_path)


@pytest.fixture
def temp_usfm_directory():
    """Create a temporary directory with multiple USFM files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create Genesis file
        gen_path = Path(temp_dir) / "01-GEN.usfm"
        with open(gen_path, 'w', encoding='utf-8') as f:
            f.write(SAMPLE_GENESIS_USFM)

        # Create Matthew file
        mat_path = Path(temp_dir) / "40-MAT.usfm"
        with open(mat_path, 'w', encoding='utf-8') as f:
            f.write(SAMPLE_MATTHEW_USFM)

        yield Path(temp_dir)


class TestParsedVerse:
    """Test the ParsedVerse dataclass."""

    def test_parsed_verse_fields(self):
        """ParsedVerse should have all required fields."""
        verse = ParsedVerse(
            book_code="genesis",
            book_name="Genesis",
            usfm_code="GEN",
            chapter=1,
            verse=1,
            raw_text="raw text",
            clean_text="clean text"
        )
        assert verse.book_code == "genesis"
        assert verse.book_name == "Genesis"
        assert verse.usfm_code == "GEN"
        assert verse.chapter == 1
        assert verse.verse == 1
        assert verse.raw_text == "raw text"
        assert verse.clean_text == "clean text"


class TestParseResult:
    """Test the ParseResult dataclass."""

    def test_empty_result(self):
        """Empty result should have zero counts."""
        result = ParseResult()
        assert result.verse_count == 0
        assert result.books_parsed == 0
        assert len(result.errors) == 0
        assert not result.success

    def test_result_with_verses(self):
        """Result with verses should report correct count."""
        result = ParseResult()
        result.verses.append(ParsedVerse(
            book_code="genesis",
            book_name="Genesis",
            usfm_code="GEN",
            chapter=1,
            verse=1,
            raw_text="raw",
            clean_text="clean"
        ))
        assert result.verse_count == 1
        assert result.success

    def test_result_with_errors(self):
        """Result with errors should not be successful."""
        result = ParseResult()
        result.verses.append(ParsedVerse(
            book_code="genesis",
            book_name="Genesis",
            usfm_code="GEN",
            chapter=1,
            verse=1,
            raw_text="raw",
            clean_text="clean"
        ))
        result.errors.append("Some error")
        assert not result.success


class TestExtractBookId:
    """Test the _extract_book_id helper function."""

    def test_extract_genesis(self):
        """Should extract GEN from Genesis file."""
        text = r"\id GEN  \n\h Genesis"
        assert _extract_book_id(text) == "GEN"

    def test_extract_matthew(self):
        """Should extract MAT from Matthew file."""
        text = r"\id MAT\n\h Matthew"
        assert _extract_book_id(text) == "MAT"

    def test_no_id_marker(self):
        """Should return None if no \id marker."""
        text = r"\h Genesis\n\c 1"
        assert _extract_book_id(text) is None

    def test_case_normalization(self):
        """Should return uppercase code."""
        text = r"\id gen"
        assert _extract_book_id(text) == "GEN"


class TestParseUSFMFile:
    """Test the parse_usfm_file function."""

    def test_parse_valid_file(self, temp_usfm_file):
        """Should parse a valid USFM file."""
        result = parse_usfm_file(temp_usfm_file)

        assert result.books_parsed == 1
        assert result.verse_count == 5  # 3 verses in ch1, 2 in ch2
        assert len(result.errors) == 0
        assert result.success

    def test_verses_have_correct_book_info(self, temp_usfm_file):
        """Parsed verses should have correct book information."""
        result = parse_usfm_file(temp_usfm_file)

        for verse in result.verses:
            assert verse.book_code == "genesis"
            assert verse.book_name == "Genesis"
            assert verse.usfm_code == "GEN"

    def test_verses_have_correct_chapters(self, temp_usfm_file):
        """Verses should have correct chapter numbers."""
        result = parse_usfm_file(temp_usfm_file)

        # First 3 verses should be chapter 1
        assert result.verses[0].chapter == 1
        assert result.verses[1].chapter == 1
        assert result.verses[2].chapter == 1

        # Last 2 verses should be chapter 2
        assert result.verses[3].chapter == 2
        assert result.verses[4].chapter == 2

    def test_verses_have_correct_verse_numbers(self, temp_usfm_file):
        """Verses should have correct verse numbers."""
        result = parse_usfm_file(temp_usfm_file)

        assert result.verses[0].verse == 1
        assert result.verses[1].verse == 2
        assert result.verses[2].verse == 3
        assert result.verses[3].verse == 1  # Chapter 2, verse 1

    def test_strongs_numbers_removed(self, temp_usfm_file):
        """Strong's numbers should be removed from clean_text."""
        result = parse_usfm_file(temp_usfm_file)

        first_verse = result.verses[0]
        assert "H7225" not in first_verse.clean_text
        assert "In the beginning" in first_verse.clean_text

    def test_file_not_found(self):
        """Should handle missing files gracefully."""
        result = parse_usfm_file("/nonexistent/path/file.usfm")

        assert result.verse_count == 0
        assert len(result.errors) > 0
        assert not result.success

    def test_file_without_id_marker(self):
        """Should handle files without \id marker."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.usfm', delete=False) as f:
            f.write(r"\c 1\n\v 1 Some text")
            temp_path = f.name

        try:
            result = parse_usfm_file(temp_path)
            assert len(result.errors) > 0
            assert "\\id" in result.errors[0].lower() or "id" in result.errors[0].lower()
        finally:
            os.unlink(temp_path)


class TestParseUSFMDirectory:
    """Test the parse_usfm_directory function."""

    def test_parse_directory(self, temp_usfm_directory):
        """Should parse all USFM files in directory."""
        result = parse_usfm_directory(temp_usfm_directory)

        assert result.books_parsed == 2  # Genesis and Matthew
        assert result.verse_count == 8  # 5 from Genesis + 3 from Matthew
        assert result.success

    def test_directory_not_found(self):
        """Should handle missing directory."""
        result = parse_usfm_directory("/nonexistent/directory")

        assert result.verse_count == 0
        assert len(result.errors) > 0
        assert not result.success

    def test_empty_directory(self):
        """Should handle directory with no USFM files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = parse_usfm_directory(temp_dir)
            assert result.verse_count == 0
            assert len(result.errors) > 0

    def test_custom_pattern(self, temp_usfm_directory):
        """Should support custom glob patterns."""
        # Only match Genesis file pattern
        result = parse_usfm_directory(temp_usfm_directory, pattern="01-*.usfm")
        assert result.books_parsed == 1


class TestIterUSFMVerses:
    """Test the iter_usfm_verses generator function."""

    def test_iter_verses(self, temp_usfm_file):
        """Should yield verses one at a time."""
        verses = list(iter_usfm_verses(temp_usfm_file))

        assert len(verses) == 5
        assert all(isinstance(v, ParsedVerse) for v in verses)

    def test_iter_is_lazy(self, temp_usfm_file):
        """Iterator should be usable lazily."""
        verse_iter = iter_usfm_verses(temp_usfm_file)

        first_verse = next(verse_iter)
        assert first_verse.chapter == 1
        assert first_verse.verse == 1


class TestRealUSFMFiles:
    """Test with real USFM files if available."""

    @pytest.fixture
    def engnet_dir(self):
        """Path to engNET USFM directory."""
        # Try multiple possible locations
        paths = [
            Path("../data/bibles/engnet_usfm"),
            Path("data/bibles/engnet_usfm")
        ]
        for path in paths:
            if path.exists():
                return path
        pytest.skip("engNET USFM files not found")

    def test_parse_real_genesis(self, engnet_dir):
        """Test parsing real Genesis file."""
        genesis_files = list(engnet_dir.glob("*GEN*.usfm"))
        if not genesis_files:
            pytest.skip("Genesis file not found")

        result = parse_usfm_file(genesis_files[0])

        # Genesis has 50 chapters and 1533 verses
        assert result.books_parsed == 1
        assert result.verse_count > 1500
        assert result.success

    def test_parse_real_matthew(self, engnet_dir):
        """Test parsing real Matthew file."""
        matthew_files = list(engnet_dir.glob("*MAT*.usfm"))
        if not matthew_files:
            pytest.skip("Matthew file not found")

        result = parse_usfm_file(matthew_files[0])

        # Matthew has 28 chapters
        assert result.books_parsed == 1
        assert result.verse_count > 1000
        assert result.success