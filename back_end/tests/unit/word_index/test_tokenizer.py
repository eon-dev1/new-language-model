"""Tests for the verse tokenizer."""

from utils.word_index.tokenizer import tokenize_verse


class TestTokenizeVerse:
    """Core tokenization behavior."""

    def test_basic_whitespace_split(self):
        assert tokenize_verse("Na komi tinoni") == ["na", "komi", "tinoni"]

    def test_lowercase(self):
        assert tokenize_verse("GOD Is Great") == ["god", "is", "great"]

    def test_strip_trailing_punctuation(self):
        assert tokenize_verse("tabu, ke...") == ["tabu", "ke"]

    def test_strip_leading_punctuation(self):
        assert tokenize_verse("(hello) [world]") == ["hello", "world"]

    def test_strip_guillemets(self):
        assert tokenize_verse("«bonjour»") == ["bonjour"]

    def test_strip_em_dash(self):
        assert tokenize_verse("word—another") == ["word", "another"]

    def test_preserve_hyphen_within_word(self):
        assert tokenize_verse("God-given") == ["god-given"]

    def test_preserve_mid_word_apostrophe(self):
        """Oceanic languages use apostrophe as glottal stop."""
        assert tokenize_verse("ta'u") == ["ta'u"]

    def test_preserve_glottal_stop_character(self):
        """U+0294 ʔ is a phonemic character in some languages."""
        assert tokenize_verse("ʔaba") == ["ʔaba"]

    def test_strip_surrounding_quotes(self):
        assert tokenize_verse("'hello'") == ["hello"]

    def test_dont_strip_apostrophe_contraction(self):
        assert tokenize_verse("don't") == ["don't"]

    def test_keep_numerals(self):
        assert tokenize_verse("3 words 16") == ["3", "words", "16"]

    def test_empty_string(self):
        assert tokenize_verse("") == []

    def test_whitespace_only(self):
        assert tokenize_verse("   \t\n  ") == []

    def test_pure_punctuation(self):
        assert tokenize_verse("... --- !!!") == []

    def test_unicode_nfc_normalization(self):
        """e + combining acute (NFD) should equal é (NFC)."""
        nfd = "e\u0301"  # e + combining acute accent
        nfc = "\u00e9"  # é precomposed
        result_nfd = tokenize_verse(nfd)
        result_nfc = tokenize_verse(nfc)
        assert result_nfd == result_nfc
        assert result_nfd == [nfc]

    def test_mixed_punctuation_and_text(self):
        assert tokenize_verse('"Hello," she said.') == ["hello", "she", "said"]

    def test_curly_quotes_stripped(self):
        assert tokenize_verse("\u201cword\u201d") == ["word"]

    def test_semicolon_and_colon(self):
        assert tokenize_verse("first; second: third") == ["first", "second", "third"]
