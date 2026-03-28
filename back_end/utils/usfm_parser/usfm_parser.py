# usfm_parser.py
"""
Core USFM parsing logic for extracting Bible verses.

Parses USFM (Unified Standard Format Markers) files and extracts structured
verse data suitable for MongoDB import.


# Import entire engnet directory
python -m utils.usfm_parser.usfm_importer \
    ../data/bibles/engnet_usfm/ \
    english \
    human

    
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Iterator

from .usfm_book_codes import usfm_code_to_book_code, usfm_code_to_book_name, is_valid_usfm_code
from .remove_usfm_markers import remove_usfm_markers

logger = logging.getLogger(__name__)


@dataclass
class ParsedVerse:
    """Represents a single parsed verse from a USFM file."""
    book_code: str          # MongoDB book code (e.g., "genesis")
    book_name: str          # Display name (e.g., "Genesis")
    usfm_code: str          # Original USFM code (e.g., "GEN")
    chapter: int
    verse: int
    raw_text: str           # Original text with USFM markers
    clean_text: str         # Cleaned text (markers removed)
    footnotes: List[str] = field(default_factory=list)  # Optional footnotes


@dataclass
class ParseResult:
    """Result of parsing one or more USFM files."""
    verses: List[ParsedVerse] = field(default_factory=list)
    books_parsed: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def verse_count(self) -> int:
        return len(self.verses)

    @property
    def success(self) -> bool:
        return self.verse_count > 0 and len(self.errors) == 0


def _extract_book_id(text: str) -> Optional[str]:
    r"""
    Extract USFM book identifier from \\id marker.

    Args:
        text: Full USFM file content

    Returns:
        USFM book code (e.g., "GEN") or None if not found
    """
    match = re.search(r'\\id\s+(\w+)', text)
    if match:
        return match.group(1).upper()
    return None


def _parse_verse_line(line: str, current_chapter: int, book_info: tuple) -> Optional[ParsedVerse]:
    """
    Parse a verse line and create a ParsedVerse object.

    Args:
        line: The line containing \v marker and verse text
        current_chapter: Current chapter number
        book_info: Tuple of (book_code, book_name, usfm_code)

    Returns:
        ParsedVerse object or None if parsing fails
    """
    book_code, book_name, usfm_code = book_info

    # Match verse marker: \v 1 text... or \v 1-3 text... (verse ranges)
    verse_match = re.match(r'\\v\s+(\d+)(?:-\d+)?\s*(.*)', line.strip())
    if not verse_match:
        return None

    verse_num = int(verse_match.group(1))
    raw_text = verse_match.group(2).strip()

    # Clean the text (remove USFM markers, Strong's numbers, etc.)
    clean_text = remove_usfm_markers(raw_text)

    return ParsedVerse(
        book_code=book_code,
        book_name=book_name,
        usfm_code=usfm_code,
        chapter=current_chapter,
        verse=verse_num,
        raw_text=raw_text,
        clean_text=clean_text
    )


def parse_usfm_file(filepath: Path | str) -> ParseResult:
    """
    Parse a single USFM file and extract all verses.

    Args:
        filepath: Path to the USFM file

    Returns:
        ParseResult containing all parsed verses
    """
    filepath = Path(filepath)
    result = ParseResult()

    if not filepath.exists():
        result.errors.append(f"File not found: {filepath}")
        return result

    logger.debug(f"Parsing USFM file: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        result.errors.append(f"Failed to read {filepath}: {e}")
        return result

    # Extract book identifier
    usfm_code = _extract_book_id(content)
    if not usfm_code:
        result.errors.append(f"No \\id marker found in {filepath}")
        return result

    if not is_valid_usfm_code(usfm_code):
        result.errors.append(f"Unknown USFM book code: {usfm_code} in {filepath}")
        return result

    book_code = usfm_code_to_book_code(usfm_code)
    book_name = usfm_code_to_book_name(usfm_code)
    book_info = (book_code, book_name, usfm_code)

    logger.info(f"Parsing {book_name} ({usfm_code}) from {filepath.name}")

    current_chapter = 0
    current_verse_parts = []  # Accumulate multi-line verse text
    current_verse_num = None

    def flush_verse():
        """Save accumulated verse text as a ParsedVerse."""
        nonlocal current_verse_parts, current_verse_num
        if current_verse_num is not None and current_verse_parts:
            raw_text = ' '.join(current_verse_parts)
            clean_text = remove_usfm_markers(raw_text)
            result.verses.append(ParsedVerse(
                book_code=book_code,
                book_name=book_name,
                usfm_code=usfm_code,
                chapter=current_chapter,
                verse=current_verse_num,
                raw_text=raw_text,
                clean_text=clean_text
            ))
        current_verse_parts = []
        current_verse_num = None

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Chapter marker
        chapter_match = re.match(r'\\c\s+(\d+)', line)
        if chapter_match:
            flush_verse()  # Save any pending verse
            current_chapter = int(chapter_match.group(1))
            logger.debug(f"Chapter {current_chapter}")
            continue

        # Verse marker - may have text on same line
        verse_match = re.match(r'\\v\s+(\d+)(?:-\d+)?\s*(.*)', line)
        if verse_match:
            flush_verse()  # Save previous verse
            current_verse_num = int(verse_match.group(1))
            verse_text = verse_match.group(2).strip()
            if verse_text:
                current_verse_parts.append(verse_text)
            continue

        # Continuation lines (text that's part of current verse)
        # Skip section headers, titles, etc.
        if current_verse_num is not None:
            # Skip certain markers that shouldn't be part of verse text
            if line.startswith(('\\s', '\\r', '\\mt', '\\h', '\\toc', '\\id')):
                continue
            # Paragraph markers followed by text
            para_match = re.match(r'\\[pqm]\d?\s*(.*)', line)
            if para_match:
                text = para_match.group(1).strip()
                if text:
                    current_verse_parts.append(text)
                continue
            # Poetry/quote markers
            if line.startswith(('\\q', '\\pi', '\\li')):
                text = re.sub(r'^\\[a-z]+\d?\s*', '', line).strip()
                if text:
                    current_verse_parts.append(text)
                continue
            # Plain continuation text (shouldn't happen often in well-formed USFM)
            if not line.startswith('\\'):
                current_verse_parts.append(line)

    # Flush any remaining verse
    flush_verse()

    result.books_parsed = 1
    logger.info(f"Parsed {len(result.verses)} verses from {book_name}")

    return result


def parse_usfm_directory(dirpath: Path | str, pattern: str = None) -> ParseResult:
    """
    Parse all USFM files in a directory.

    Args:
        dirpath: Path to directory containing USFM files
        pattern: Glob pattern for USFM files. If None, auto-detects common extensions.

    Returns:
        ParseResult containing all parsed verses from all files
    """
    dirpath = Path(dirpath)
    result = ParseResult()

    if not dirpath.exists():
        result.errors.append(f"Directory not found: {dirpath}")
        return result

    if not dirpath.is_dir():
        result.errors.append(f"Not a directory: {dirpath}")
        return result

    # Auto-detect file extension if pattern not specified
    if pattern is None:
        for try_pattern in ["*.usfm", "*.SFM", "*.sfm", "*.USFM"]:
            usfm_files = list(dirpath.glob(try_pattern))
            if usfm_files:
                pattern = try_pattern
                logger.info(f"Auto-detected USFM pattern: {pattern}")
                break
        else:
            pattern = "*.usfm"  # Default fallback

    usfm_files = sorted(dirpath.glob(pattern))
    if not usfm_files:
        result.errors.append(f"No USFM files found in {dirpath} matching {pattern}")
        return result

    logger.info(f"Found {len(usfm_files)} USFM files in {dirpath}")

    for usfm_file in usfm_files:
        file_result = parse_usfm_file(usfm_file)
        result.verses.extend(file_result.verses)
        result.books_parsed += file_result.books_parsed
        result.errors.extend(file_result.errors)

    logger.info(f"Total: {result.verse_count} verses from {result.books_parsed} books")
    return result


def iter_usfm_verses(filepath: Path | str) -> Iterator[ParsedVerse]:
    """
    Iterator that yields verses one at a time from a USFM file.
    Memory-efficient for large files.

    Args:
        filepath: Path to the USFM file

    Yields:
        ParsedVerse objects
    """
    result = parse_usfm_file(filepath)
    yield from result.verses


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python usfm_parser.py <usfm_file_or_directory>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file():
        result = parse_usfm_file(path)
    elif path.is_dir():
        result = parse_usfm_directory(path)
    else:
        print(f"Path not found: {path}")
        sys.exit(1)

    print(f"\nParsing Results:")
    print(f"  Books parsed: {result.books_parsed}")
    print(f"  Verses extracted: {result.verse_count}")
    print(f"  Errors: {len(result.errors)}")

    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")

    if result.verses:
        print(f"\nFirst 3 verses:")
        for verse in result.verses[:3]:
            print(f"  {verse.book_name} {verse.chapter}:{verse.verse}")
            print(f"    {verse.clean_text[:80]}...")