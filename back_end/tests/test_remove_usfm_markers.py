# tests/test_remove_usfm_markers.py
"""Tests for USFM marker removal functionality."""

import pytest
from utils.usfm_parser.remove_usfm_markers import remove_usfm_markers


class TestStrongsNumberRemoval:
    """Test removal of Strong's concordance numbers."""

    def test_hebrew_strongs_removal(self):
        """Remove Hebrew Strong's numbers (H####)."""
        text = r'\w In the beginning|strong="H7225"\w* \w God|strong="H0430"\w*'
        result = remove_usfm_markers(text)
        assert result == "In the beginning God"
        assert "H7225" not in result
        assert "H0430" not in result

    def test_greek_strongs_removal(self):
        """Remove Greek Strong's numbers (G####)."""
        text = r'\w love|strong="G0026"\w* \w God|strong="G2316"\w*'
        result = remove_usfm_markers(text)
        assert result == "love God"
        assert "G0026" not in result

    def test_nested_word_markers(self):
        """Handle nested \+w markers."""
        text = r'\+w In|strong="G1722"\+w* test'
        result = remove_usfm_markers(text)
        assert "In" in result
        assert "G1722" not in result


class TestFootnoteRemoval:
    """Test removal of footnote markers."""

    def test_simple_footnote_removed(self):
        """Footnotes should be completely removed."""
        text = r'text before \f + \ft footnote content\f* text after'
        result = remove_usfm_markers(text)
        assert "footnote content" not in result
        assert "text before" in result
        assert "text after" in result

    def test_multiple_footnotes(self):
        """Multiple footnotes should all be removed."""
        text = r'word1 \f + note1\f* word2 \f + note2\f* word3'
        result = remove_usfm_markers(text)
        assert "note1" not in result
        assert "note2" not in result


class TestCrossReferenceRemoval:
    """Test removal of cross-reference markers."""

    def test_cross_reference_removed(self):
        """Cross-references should be completely removed."""
        text = r'verse text \x + \xo 1:1 \xt Gen 1:1\x* more text'
        result = remove_usfm_markers(text)
        assert "Gen 1:1" not in result
        assert "verse text" in result
        assert "more text" in result


class TestFigureRemoval:
    """Test removal of figure markers."""

    def test_figure_removed(self):
        """Figure markers should be removed."""
        text = r'text \fig description|alt="image"\fig* more text'
        result = remove_usfm_markers(text)
        assert "description" not in result


class TestFormattingPreservation:
    """Test that formatting markers preserve their content."""

    def test_italic_text_preserved(self):
        """Text inside \it markers should be kept."""
        text = r'\it emphasized text\it*'
        result = remove_usfm_markers(text)
        assert "emphasized text" in result

    def test_bold_text_preserved(self):
        """Text inside \bd markers should be kept."""
        text = r'\bd bold text\bd*'
        result = remove_usfm_markers(text)
        assert "bold text" in result

    def test_small_caps_preserved(self):
        """Text inside \sc markers should be kept."""
        text = r'\sc LORD\sc*'
        result = remove_usfm_markers(text)
        assert "LORD" in result


class TestVerseMarkerRemoval:
    """Test removal of verse markers."""

    def test_verse_marker_removed(self):
        """Verse markers and numbers should be removed."""
        text = r'\v 1 In the beginning'
        result = remove_usfm_markers(text)
        assert result == "In the beginning"

    def test_verse_with_range_removed(self):
        """Verse ranges should be handled."""
        text = r'\v 2-3 Combined verses'
        result = remove_usfm_markers(text)
        # The marker and number should be removed
        assert "Combined verses" in result


class TestWhitespaceNormalization:
    """Test that whitespace is normalized."""

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces should become single space."""
        text = r'\w word1|strong="H1"\w*    \w word2|strong="H2"\w*'
        result = remove_usfm_markers(text)
        assert "  " not in result  # No double spaces

    def test_leading_trailing_stripped(self):
        """Leading and trailing whitespace should be stripped."""
        text = r'  \w word|strong="H1"\w*  '
        result = remove_usfm_markers(text)
        assert result == "word"


class TestEdgeCases:
    """Test edge cases and special inputs."""

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert remove_usfm_markers("") == ""

    def test_no_markers(self):
        """Text without markers should pass through unchanged."""
        text = "Plain text without any markers"
        result = remove_usfm_markers(text)
        assert result == text

    def test_only_markers(self):
        """Text with only markers that get removed."""
        text = r'\f + footnote only\f*'
        result = remove_usfm_markers(text)
        assert result == ""

    def test_unicode_preserved(self):
        """Unicode characters should be preserved."""
        text = r'\w אֱלֹהִים|strong="H0430"\w*'
        result = remove_usfm_markers(text)
        assert "אֱלֹהִים" in result


class TestRealWorldExamples:
    """Test with real USFM content from engNET."""

    def test_genesis_1_1(self):
        """Test Genesis 1:1 USFM format."""
        text = (
            r'\w In the beginning|strong="H7225"\w* '
            r'\w God|strong="H0430"\w* '
            r'\w created|strong="H1254"\w* '
            r'\w the heavens|strong="H8064"\w* '
            r'\w and the|strong="H0853"\w* '
            r'\w earth|strong="H0776"\w*.'
        )
        result = remove_usfm_markers(text)
        assert result == "In the beginning God created the heavens and the earth."

    def test_genesis_1_2(self):
        """Test Genesis 1:2 with more complex markers."""
        text = (
            r'\w Now|strong="H1961"\w* '
            r'\w the earth|strong="H0776"\w* '
            r'\w was without shape|strong="H8414"\w* '
            r'\w and empty|strong="H0922"\w*'
        )
        result = remove_usfm_markers(text)
        assert result == "Now the earth was without shape and empty"

    def test_mixed_markers(self):
        """Test text with multiple marker types."""
        text = (
            r'\v 1 \w In|strong="H1"\w* the '
            r'\it beginning\it* '
            r'\f + footnote\f* '
            r'\w God|strong="H2"\w*'
        )
        result = remove_usfm_markers(text)
        assert "In" in result
        assert "beginning" in result
        assert "God" in result
        assert "footnote" not in result