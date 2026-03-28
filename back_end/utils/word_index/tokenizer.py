"""
Verse tokenizer for word index construction.

Whitespace-based tokenizer with Unicode NFC normalization and
punctuation stripping. Preserves mid-word apostrophes and glottal
stops (phonemic in Oceanic languages like Bughotu and Kope).
"""

import re
import unicodedata


# Characters that act as word separators (split on these in addition to whitespace)
_WORD_SEPARATORS = re.compile(r"[\s\u2014\u2013/]+")  # whitespace, em-dash, en-dash, slash

# Punctuation to strip from word boundaries (NOT mid-word).
# Excludes apostrophe/glottal stop — handled separately to preserve mid-word usage.
_BOUNDARY_PUNCT = re.compile(
    r"^[.,;:!?\"\u201c\u201d\u2018\u2019\u0027«»\-\(\)\[\]{}<>]+|"
    r"[.,;:!?\"\u201c\u201d\u2018\u2019\u0027«»\-\(\)\[\]{}<>]+$"
)

# Mid-word apostrophe pattern: strip only if at very start or end of token
# (e.g., 'word' → word), but preserve in ta'u, don't, ʔa
_LEADING_TRAILING_QUOTE = re.compile(r"^['\u2018\u2019]+|['\u2018\u2019]+$")


def tokenize_verse(text: str) -> list[str]:
    """
    Tokenize verse text into lowercase, NFC-normalized words.

    Args:
        text: Raw verse text (may contain punctuation, mixed case)

    Returns:
        List of lowercase tokens with punctuation stripped.
        Empty/whitespace input returns [].

    Examples:
        >>> tokenize_verse("Na komi tinoni tabu, ke...")
        ['na', 'komi', 'tinoni', 'tabu', 'ke']
        >>> tokenize_verse("God-given")
        ['god-given']
        >>> tokenize_verse("ta'u")
        ["ta'u"]
        >>> tokenize_verse("")
        []
    """
    if not text or not text.strip():
        return []

    # Unicode NFC normalization
    text = unicodedata.normalize("NFC", text)

    tokens = []
    for raw in _WORD_SEPARATORS.split(text):
        # Strip boundary punctuation (heavy chars: em-dash, guillemets, parens, etc.)
        word = _BOUNDARY_PUNCT.sub("", raw)

        # Strip leading/trailing quotes/apostrophes, but only if the stripped
        # result still contains characters (preserves mid-word apostrophes)
        stripped = _LEADING_TRAILING_QUOTE.sub("", word)
        if stripped:
            word = stripped

        # Lowercase
        word = word.lower()

        # Skip empty tokens and pure-punctuation remnants
        if not word:
            continue

        # Keep the glottal stop character ʔ (U+0294) as-is
        tokens.append(word)

    return tokens
