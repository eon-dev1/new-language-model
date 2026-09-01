# constants.py
"""
Centralized constants for the NLM backend.

Provides enums and constants for collection names and other magic strings
used throughout the codebase.
"""

from enum import Enum


class Collection(str, Enum):
    """MongoDB collection names."""
    LANGUAGES = "languages"
    BASE_STRUCTURE_BIBLE = "base_structure_bible"  # Canonical structure (generator scripts)
    BIBLE_BOOKS = "bible_books"  # Language-specific book metadata
    BIBLE_TEXTS = "bible_texts"
    DICTIONARIES = "dictionaries"
    GRAMMAR_SYSTEMS = "grammar_systems"
    WORD_INDEX = "word_index"
    PHRASE_INDEX = "phrase_index"
    LANGUAGE_NOTES = "language_notes"
    CORRECTION_LOG = "correction_log"
