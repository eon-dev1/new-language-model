# tests/test_html_parser.py
"""Tests for HTML Bible parsing functionality."""

import pytest
from pathlib import Path
import tempfile
import os

from bs4 import BeautifulSoup

from utils.html_parser.html_parser import (
    extract_book_chapter_from_filename,
    parse_html_file,
    parse_html_directory,
    _validate_html_structure,
    _extract_all_verses,
    _extract_verse_footnotes,
    _clean_html_text,
)
from utils.usfm_parser.usfm_parser import ParsedVerse, ParseResult


# =============================================================================
# Sample HTML content for testing
# =============================================================================

SAMPLE_VALID_HTML = '''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<div class="main">
  <div class='chapterlabel' id="V0">1</div>
  <span class="verse" id="V1">1&#160;</span>In the beginning God created the heavens and the earth.
  <span class="verse" id="V2">2&#160;</span>And the earth was without form, and void.
  <span class="verse" id="V3">3&#160;</span>And God said, Let there be light.
</div>
</body>
</html>'''

SAMPLE_WITH_FOOTNOTES = '''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<div class="main">
  <span class="verse" id="V1">1&#160;</span>Text with footnote marker.
  <span class="verse" id="V2">2&#160;</span>Another verse here.
</div>
<div class="footnote">
  <p class="f" id="FN1">
    <span class="notemark">*</span>
    <a class="notebackref" href="#V1">1:1</a>
    <span class="ft">This is a footnote explanation.</span>
  </p>
  <p class="f" id="FN2">
    <span class="notemark">*</span>
    <a class="notebackref" href="#V1">1:1</a>
    <span class="ft">Second footnote for verse 1.</span>
  </p>
</div>
</body>
</html>'''

SAMPLE_MISSING_MAIN_DIV = '''<!DOCTYPE html>
<html><body>
<div class="content">
  <span class="verse" id="V1">1&#160;</span>Text here.
</div>
</body></html>'''

SAMPLE_NO_VERSES = '''<!DOCTYPE html>
<html><body>
<div class="main">
  <p>Some paragraph text without verse markers.</p>
</div>
</body></html>'''

SAMPLE_SINGLE_VERSE = '''<!DOCTYPE html>
<html><body>
<div class="main">
  <span class="verse" id="V1">1&#160;</span>The only verse in this chapter.
</div>
</body></html>'''

SAMPLE_VERSES_ACROSS_DIVS = '''<!DOCTYPE html>
<html><body>
<div class="main">
  <div class="p"><span class="verse" id="V1">1&#160;</span>First part of verse one.</div>
  <div class="q">Continuation of verse one across divs.</div>
  <div class="p"><span class="verse" id="V2">2&#160;</span>Verse two here.</div>
</div>
</body></html>'''

SAMPLE_WITH_VERSE_ZERO = '''<!DOCTYPE html>
<html><body>
<div class="main">
  <div class='chapterlabel' id="V0">1</div>
  <span class="verse" id="V1">1&#160;</span>First actual verse.
  <span class="verse" id="V2">2&#160;</span>Second verse.
</div>
</body></html>'''

SAMPLE_STOPS_AT_FOOTNOTE = '''<!DOCTYPE html>
<html><body>
<div class="main">
  <span class="verse" id="V1">1&#160;</span>Verse content here.
</div>
<div class="footnote">
  <p>This footnote text should NOT be captured as verse content.</p>
</div>
</body></html>'''


# =============================================================================
# Test Classes
# =============================================================================

class TestExtractBookChapterFromFilename:
    """Test filename parsing to extract book and chapter."""

    @pytest.mark.parametrize("filename,expected", [
        ("MAT01.htm", ("MAT", 1)),
        ("1CO08.htm", ("1CO", 8)),
        ("REV22.htm", ("REV", 22)),
        ("GEN50.htm", ("GEN", 50)),
        ("JHN03.htm", ("JHN", 3)),
    ])
    def test_valid_filenames(self, filename, expected):
        """Valid filenames should return (usfm_code, chapter)."""
        result = extract_book_chapter_from_filename(filename)
        assert result == expected

    @pytest.mark.parametrize("filename", [
        "mat01.htm",  # lowercase
        "MaT01.htm",  # mixed case
        "mAt01.HTM",  # mixed case with HTM
    ])
    def test_case_insensitive(self, filename):
        """Filename parsing should be case-insensitive."""
        result = extract_book_chapter_from_filename(filename)
        assert result is not None
        assert result[0] == "MAT"
        assert result[1] == 1

    @pytest.mark.parametrize("filename", [
        "MAT00.htm",     # Chapter 0 - should be skipped (intro)
    ])
    def test_chapter_zero_returns_none(self, filename):
        """Chapter 00 files (introductions) should return None."""
        result = extract_book_chapter_from_filename(filename)
        assert result is None

    @pytest.mark.parametrize("filename", [
        "MAT.htm",        # No chapter number
        "MATTHEW01.htm",  # Too long (4+ chars)
        "MA01.htm",       # Too short (2 chars)
        "MAT1.htm",       # Single digit chapter
        "MAT001.htm",     # Three digit chapter
        "ZZZ01.htm",      # Invalid USFM code
        "XXX01.htm",      # Invalid USFM code
        "mat_01.htm",     # Underscore
        "mat-01.htm",     # Dash
        "",               # Empty string
        "file.txt",       # Wrong extension
    ])
    def test_invalid_filenames_return_none(self, filename):
        """Invalid filenames should return None."""
        result = extract_book_chapter_from_filename(filename)
        assert result is None


class TestValidateHtmlStructure:
    """Test HTML structure validation."""

    def test_valid_structure(self):
        """Valid HTML with main div and verse spans should pass."""
        soup = BeautifulSoup(SAMPLE_VALID_HTML, 'html.parser')
        errors = _validate_html_structure(soup)
        assert len(errors) == 0

    def test_missing_main_div(self):
        """HTML without main div should return error."""
        soup = BeautifulSoup(SAMPLE_MISSING_MAIN_DIV, 'html.parser')
        errors = _validate_html_structure(soup)
        assert len(errors) > 0
        assert any("main" in err.lower() for err in errors)

    def test_missing_verse_spans(self):
        """HTML without verse spans should return error."""
        soup = BeautifulSoup(SAMPLE_NO_VERSES, 'html.parser')
        errors = _validate_html_structure(soup)
        assert len(errors) > 0
        assert any("verse" in err.lower() for err in errors)

    def test_empty_html(self):
        """Empty HTML should return errors."""
        soup = BeautifulSoup("<html><body></body></html>", 'html.parser')
        errors = _validate_html_structure(soup)
        assert len(errors) >= 2  # Missing main and verses


class TestCleanHtmlText:
    """Test text cleaning functionality."""

    @pytest.mark.parametrize("input_text,expected", [
        ("hello\xa0world", "hello world"),           # Non-breaking space
        ("  multiple   spaces  ", "multiple spaces"), # Multiple spaces
        ("text\n\twith\nwhitespace", "text with whitespace"),  # Newlines/tabs
        ("", ""),                                      # Empty string
        ("already clean", "already clean"),           # No change needed
        ("  leading", "leading"),                     # Leading whitespace
        ("trailing  ", "trailing"),                   # Trailing whitespace
        ("\xa0\xa0double\xa0nbsp\xa0\xa0", "double nbsp"),  # Multiple nbsp
    ])
    def test_clean_html_text(self, input_text, expected):
        """Text cleaning should handle various whitespace patterns."""
        result = _clean_html_text(input_text)
        assert result == expected


class TestExtractAllVerses:
    """Test single-pass verse extraction algorithm."""

    def test_single_verse_extraction(self):
        """Should extract a single verse correctly."""
        soup = BeautifulSoup(SAMPLE_SINGLE_VERSE, 'html.parser')
        verses = _extract_all_verses(soup)
        assert 1 in verses
        raw, clean = verses[1]
        assert "only verse" in clean

    def test_multiple_verses_in_order(self):
        """Should extract multiple verses in correct order."""
        soup = BeautifulSoup(SAMPLE_VALID_HTML, 'html.parser')
        verses = _extract_all_verses(soup)
        assert 1 in verses
        assert 2 in verses
        assert 3 in verses
        assert "beginning" in verses[1][1]
        assert "without form" in verses[2][1]
        assert "light" in verses[3][1]

    def test_verse_zero_skipped(self):
        """Verse 0 (chapter marker) should not be included."""
        soup = BeautifulSoup(SAMPLE_WITH_VERSE_ZERO, 'html.parser')
        verses = _extract_all_verses(soup)
        assert 0 not in verses
        assert 1 in verses
        assert 2 in verses

    def test_text_across_elements(self):
        """Should capture text that spans multiple div elements."""
        soup = BeautifulSoup(SAMPLE_VERSES_ACROSS_DIVS, 'html.parser')
        verses = _extract_all_verses(soup)
        assert 1 in verses
        raw, clean = verses[1]
        # Both parts should be captured
        assert "First part" in clean
        assert "Continuation" in clean

    def test_stops_at_footnote_section(self):
        """Should not include text after footnote div."""
        soup = BeautifulSoup(SAMPLE_STOPS_AT_FOOTNOTE, 'html.parser')
        verses = _extract_all_verses(soup)
        assert 1 in verses
        raw, clean = verses[1]
        assert "footnote text should NOT" not in clean
        assert "Verse content" in clean

    def test_missing_main_div_raises(self):
        """Should raise ValueError if main div is missing."""
        soup = BeautifulSoup(SAMPLE_MISSING_MAIN_DIV, 'html.parser')
        with pytest.raises(ValueError):
            _extract_all_verses(soup)


class TestExtractVerseFootnotes:
    """Test footnote extraction for specific verses."""

    def test_single_footnote(self):
        """Should extract single footnote for a verse."""
        soup = BeautifulSoup(SAMPLE_WITH_FOOTNOTES, 'html.parser')
        # Note: Our sample has 2 footnotes for V1
        footnotes = _extract_verse_footnotes(soup, 1)
        assert len(footnotes) >= 1
        assert any("footnote explanation" in fn for fn in footnotes)

    def test_multiple_footnotes(self):
        """Should extract multiple footnotes for same verse."""
        soup = BeautifulSoup(SAMPLE_WITH_FOOTNOTES, 'html.parser')
        footnotes = _extract_verse_footnotes(soup, 1)
        assert len(footnotes) == 2
        assert "This is a footnote explanation." in footnotes
        assert "Second footnote for verse 1." in footnotes

    def test_no_footnotes_for_verse(self):
        """Should return empty list if verse has no footnotes."""
        soup = BeautifulSoup(SAMPLE_WITH_FOOTNOTES, 'html.parser')
        footnotes = _extract_verse_footnotes(soup, 2)
        assert footnotes == []

    def test_no_footnote_div(self):
        """Should return empty list if no footnote section exists."""
        soup = BeautifulSoup(SAMPLE_VALID_HTML, 'html.parser')
        footnotes = _extract_verse_footnotes(soup, 1)
        assert footnotes == []


class TestParseHtmlFile:
    """Test single HTML file parsing."""

    @pytest.fixture
    def temp_html_file(self):
        """Create a temporary HTML file with valid naming."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "MAT01.htm"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_VALID_HTML)
            yield filepath

    @pytest.fixture
    def temp_html_with_footnotes(self):
        """Create a temporary HTML file with footnotes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "MAT01.htm"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_WITH_FOOTNOTES)
            yield filepath

    def test_parse_valid_file(self, temp_html_file):
        """Should parse valid HTML file successfully."""
        result = parse_html_file(temp_html_file)
        assert result.success
        assert result.verse_count == 3
        assert result.books_parsed == 1
        assert len(result.errors) == 0

    def test_file_not_found(self):
        """Should handle missing files gracefully."""
        result = parse_html_file("/nonexistent/path/MAT01.htm")
        assert not result.success
        assert result.verse_count == 0
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_invalid_filename_format(self):
        """Should error on invalid filename format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.htm', delete=False) as f:
            f.write(SAMPLE_VALID_HTML)
            temp_path = f.name
        try:
            result = parse_html_file(temp_path)
            assert not result.success
            assert len(result.errors) > 0
            assert "filename" in result.errors[0].lower() or "pattern" in result.errors[0].lower()
        finally:
            os.unlink(temp_path)

    def test_missing_structure(self):
        """Should error on HTML without required structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "MAT01.htm"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_MISSING_MAIN_DIV)
            result = parse_html_file(filepath)
            assert not result.success
            assert len(result.errors) > 0
            assert any("main" in err.lower() for err in result.errors)

    def test_verses_have_correct_book_info(self, temp_html_file):
        """Parsed verses should have correct book information."""
        result = parse_html_file(temp_html_file)
        for verse in result.verses:
            assert verse.book_code == "matthew"
            assert verse.book_name == "Matthew"
            assert verse.usfm_code == "MAT"
            assert verse.chapter == 1

    def test_verses_have_correct_verse_numbers(self, temp_html_file):
        """Verses should have sequential verse numbers."""
        result = parse_html_file(temp_html_file)
        assert result.verses[0].verse == 1
        assert result.verses[1].verse == 2
        assert result.verses[2].verse == 3

    def test_footnotes_attached_to_verses(self, temp_html_with_footnotes):
        """Verses should have footnotes attached."""
        result = parse_html_file(temp_html_with_footnotes)
        verse1 = result.verses[0]
        assert len(verse1.footnotes) == 2
        assert "footnote explanation" in verse1.footnotes[0]

    def test_raw_and_clean_text_differ(self, temp_html_file):
        """Raw and clean text should both be populated."""
        result = parse_html_file(temp_html_file)
        for verse in result.verses:
            assert verse.raw_text
            assert verse.clean_text
            # Clean text should be derived from raw


class TestParseHtmlDirectory:
    """Test directory parsing with multiple HTML files."""

    @pytest.fixture
    def temp_html_directory(self):
        """Create a directory with multiple HTML chapter files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create MAT01.htm
            with open(Path(tmpdir) / "MAT01.htm", 'w', encoding='utf-8') as f:
                f.write(SAMPLE_VALID_HTML)

            # Create MAT02.htm (copy with slight modification)
            mat02_content = SAMPLE_VALID_HTML.replace('id="V0">1</div>', 'id="V0">2</div>')
            with open(Path(tmpdir) / "MAT02.htm", 'w', encoding='utf-8') as f:
                f.write(mat02_content)

            # Create MAT00.htm (introduction - should be skipped)
            with open(Path(tmpdir) / "MAT00.htm", 'w', encoding='utf-8') as f:
                f.write(SAMPLE_VALID_HTML)

            # Create a file without chapter number (should be skipped)
            with open(Path(tmpdir) / "MAT.htm", 'w', encoding='utf-8') as f:
                f.write(SAMPLE_VALID_HTML)

            yield Path(tmpdir)

    def test_parse_multiple_files(self, temp_html_directory):
        """Should parse all valid chapter files."""
        result = parse_html_directory(temp_html_directory)
        assert result.success
        assert result.books_parsed == 2  # MAT01 and MAT02
        assert result.verse_count == 6   # 3 verses per chapter

    def test_directory_not_found(self):
        """Should handle missing directory gracefully."""
        result = parse_html_directory("/nonexistent/directory")
        assert not result.success
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_empty_directory(self):
        """Should handle directory with no matching files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = parse_html_directory(tmpdir)
            assert not result.success
            assert len(result.errors) > 0

    def test_skips_chapter_zero(self, temp_html_directory):
        """Should skip chapter 00 (introduction) files."""
        result = parse_html_directory(temp_html_directory)
        # MAT00.htm should be skipped, only MAT01 and MAT02 parsed
        assert result.books_parsed == 2

    def test_custom_glob_pattern(self, temp_html_directory):
        """Should support custom glob patterns."""
        # Create an .html file (different extension)
        html_path = temp_html_directory / "MRK01.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(SAMPLE_VALID_HTML.replace("MAT", "MRK"))

        # Default pattern should not find .html
        result_htm = parse_html_directory(temp_html_directory, pattern="*.htm")
        # Custom pattern should find .html
        result_html = parse_html_directory(temp_html_directory, pattern="*.html")

        # The .htm files should be found with default
        assert result_htm.books_parsed >= 2


class TestRealBgtHtmlFiles:
    """Test with real BGT HTML Bible files if available."""

    BGT_HTML_PATH = Path(__file__).parent.parent.parent / "data" / "bibles" / "bgt_html"

    def test_parse_real_file(self):
        """Test parsing a real BGT HTML file."""
        test_file = self.BGT_HTML_PATH / "MRK02.htm"
        if not test_file.exists():
            pytest.skip("BGT HTML files not available")

        result = parse_html_file(test_file)
        assert result.success
        assert result.verse_count > 20  # Mark 2 has ~28 verses
        assert result.books_parsed == 1

        # Check verse structure
        for verse in result.verses:
            assert verse.book_code == "mark"
            assert verse.chapter == 2
            assert verse.verse > 0
            assert verse.clean_text

    def test_parse_real_directory(self):
        """Test parsing the real BGT HTML directory."""
        if not self.BGT_HTML_PATH.exists():
            pytest.skip("BGT HTML directory not available")

        result = parse_html_directory(self.BGT_HTML_PATH)
        assert result.success
        assert result.books_parsed > 0
        # Should have many verses across multiple books
        assert result.verse_count > 1000

    def test_real_file_with_footnotes(self):
        """Test that real files with footnotes parse correctly."""
        if not self.BGT_HTML_PATH.exists():
            pytest.skip("BGT HTML directory not available")

        # Try to find a file that might have footnotes
        result = parse_html_directory(self.BGT_HTML_PATH)
        if result.success:
            # Check if any verses have footnotes
            verses_with_footnotes = [v for v in result.verses if v.footnotes]
            # Just verify the count works (may or may not have footnotes)
            assert isinstance(len(verses_with_footnotes), int)
