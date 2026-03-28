# test_bible_chapter_verses.py
"""
Unit test for BIBLE_CHAPTER_VERSES data integrity.

Validates the static chapter/verse table used by the USFM fallback in
bible_books.py. No DB connection required.
"""


def test_bible_chapter_verses_has_correct_counts():
    from utils.bible_generator.chapter_verse_numbers import BIBLE_CHAPTER_VERSES
    assert len(BIBLE_CHAPTER_VERSES["Genesis"]) == 50
    assert len(BIBLE_CHAPTER_VERSES["Revelation"]) == 22
    assert len(BIBLE_CHAPTER_VERSES["Psalms"]) == 150
    assert len(BIBLE_CHAPTER_VERSES["Obadiah"]) == 1
    assert len(BIBLE_CHAPTER_VERSES["Song of Solomon"]) == 8
