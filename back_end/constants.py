# constants.py
"""
Centralized constants for the NLM backend.

Provides enums and constants for collection names, translation types,
and other magic strings used throughout the codebase.
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


class TranslationType(str, Enum):
    """Translation type identifiers for dual-level content."""
    HUMAN = "human"
    AI = "ai"
