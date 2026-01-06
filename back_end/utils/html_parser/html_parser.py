# html_parser.py
"""
HTML Bible parser for extracting verses from HTML-format Bible files.

Parses HTML files (like those from DBL or other sources) and extracts
structured verse data suitable for MongoDB import.

Expected HTML structure:
- Filename pattern: {BookCode}{ChapterNumber}.htm (e.g., MAT01.htm, JHN03.htm)
- Verses marked with: <span class="verse" id="V{n}">
- Content in: <div class="main">
- Footnotes in: <div class="footnote"> with <p class="f"> elements
"""

import re
import logging
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag

# Reuse from USFM parser
from utils.usfm_parser.usfm_parser import ParsedVerse, ParseResult
from utils.usfm_parser.usfm_book_codes import (
    usfm_code_to_book_code,
    usfm_code_to_book_name,
    is_valid_usfm_code
)

logger = logging.getLogger(__name__)

# Filename pattern: MAT01.htm, JHN03.htm (case-insensitive)
HTML_FILENAME_PATTERN = re.compile(r'^([A-Z0-9]{3})(\d{2})\.htm$', re.IGNORECASE)


def extract_book_chapter_from_filename(filename: str) -> Optional[tuple[str, int]]:
    """
    Extract book code and chapter from filename like 'MAT01.htm'.

    Args:
        filename: HTML filename

    Returns:
        Tuple of (usfm_code, chapter_number) or None if invalid
    """
    match = HTML_FILENAME_PATTERN.match(filename)
    if match:
        usfm_code = match.group(1).upper()
        chapter = int(match.group(2))
        if is_valid_usfm_code(usfm_code) and chapter > 0:
            return usfm_code, chapter
    return None


def _validate_html_structure(soup: BeautifulSoup) -> List[str]:
    """
    Validate expected HTML structure, return list of errors.

    Args:
        soup: Parsed BeautifulSoup object

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    if not soup.find('div', class_='main'):
        errors.append("Missing <div class='main'> - cannot locate content area")
    if not soup.find_all('span', class_='verse'):
        errors.append("No <span class='verse'> elements found - cannot identify verses")
    return errors


def _extract_all_verses(soup: BeautifulSoup) -> dict[int, tuple[str, str]]:
    """
    Single-pass O(n) extraction of all verse texts.

    Iterates through descendants once, accumulating text between verse markers.
    Handles cross-div text spans correctly.

    Args:
        soup: Parsed BeautifulSoup object

    Returns:
        Dict mapping verse_num -> (raw_text, clean_text)

    Raises:
        ValueError: If expected structure not found
    """
    main_div = soup.find('div', class_='main')
    if not main_div:
        raise ValueError("No <div class='main'> found - unexpected HTML structure")

    verses = {}
    current_verse = None
    current_text = []

    for element in main_div.descendants:
        if isinstance(element, Tag):
            # Check for verse span
            if element.name == 'span' and 'verse' in element.get('class', []):
                # Save previous verse
                if current_verse is not None and current_verse > 0:
                    raw = ' '.join(current_text)
                    verses[current_verse] = (raw, _clean_html_text(raw))
                    current_text = []

                # Start new verse
                verse_id = element.get('id', '')
                if verse_id.startswith('V'):
                    try:
                        current_verse = int(verse_id[1:])
                    except ValueError:
                        current_verse = None
                else:
                    current_verse = None

            # Stop at footnote section
            elif element.name == 'div' and 'footnote' in element.get('class', []):
                break

        elif isinstance(element, NavigableString):
            # Accumulate text if we're in a verse
            if current_verse and current_verse > 0:
                # Skip text inside verse spans (the verse number itself)
                parent = element.parent
                if parent and parent.name == 'span' and 'verse' in parent.get('class', []):
                    continue
                text = str(element).strip()
                if text:
                    current_text.append(text)

    # Save last verse
    if current_verse is not None and current_verse > 0:
        raw = ' '.join(current_text)
        verses[current_verse] = (raw, _clean_html_text(raw))

    return verses


def _clean_html_text(raw_text: str) -> str:
    """
    Remove HTML artifacts, normalize whitespace.

    Args:
        raw_text: Raw extracted text

    Returns:
        Cleaned text
    """
    text = raw_text.replace('\xa0', ' ')  # Non-breaking space
    text = re.sub(r'\s+', ' ', text)       # Normalize whitespace
    return text.strip()


def _extract_verse_footnotes(soup: BeautifulSoup, verse_num: int) -> List[str]:
    """
    Extract footnotes for a specific verse from bottom footnote section.

    Args:
        soup: Parsed BeautifulSoup object
        verse_num: Verse number to find footnotes for

    Returns:
        List of footnote text strings
    """
    footnotes = []
    footnote_div = soup.find('div', class_='footnote')
    if not footnote_div:
        return footnotes

    for p in footnote_div.find_all('p', class_='f'):
        backref = p.find('a', class_='notebackref')
        if backref and backref.get('href') == f'#V{verse_num}':
            ft_span = p.find('span', class_='ft')
            if ft_span:
                footnotes.append(ft_span.get_text(strip=True))

    return footnotes


def parse_html_file(filepath: Path | str) -> ParseResult:
    """
    Parse a single HTML Bible chapter file.

    Args:
        filepath: Path to the HTML file

    Returns:
        ParseResult containing all parsed verses
    """
    filepath = Path(filepath)
    result = ParseResult()

    if not filepath.exists():
        result.errors.append(f"File not found: {filepath}")
        return result

    # Extract book/chapter from filename
    extracted = extract_book_chapter_from_filename(filepath.name)
    if not extracted:
        result.errors.append(f"Invalid filename format: {filepath.name} (expected pattern: MAT01.htm)")
        return result

    usfm_code, chapter = extracted
    book_code = usfm_code_to_book_code(usfm_code)
    book_name = usfm_code_to_book_name(usfm_code)

    logger.debug(f"Parsing HTML file: {filepath} ({book_name} {chapter})")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
    except Exception as e:
        result.errors.append(f"Failed to read {filepath}: {e}")
        return result

    # Validate HTML structure - emit clear errors if unexpected
    structure_errors = _validate_html_structure(soup)
    if structure_errors:
        for err in structure_errors:
            result.errors.append(f"{filepath.name}: {err}")
        return result

    # Single-pass extraction of all verses (O(n) algorithm)
    try:
        verse_texts = _extract_all_verses(soup)
    except ValueError as e:
        result.errors.append(f"{filepath.name}: {e}")
        return result

    if not verse_texts:
        result.errors.append(f"{filepath.name}: No verses extracted")
        return result

    # Build ParsedVerse objects with footnotes
    for verse_num, (raw_text, clean_text) in sorted(verse_texts.items()):
        if verse_num == 0:  # Chapter marker, skip
            continue
        if not clean_text:  # Skip empty verses
            continue

        footnotes = _extract_verse_footnotes(soup, verse_num)

        verse = ParsedVerse(
            book_code=book_code,
            book_name=book_name,
            usfm_code=usfm_code,
            chapter=chapter,
            verse=verse_num,
            raw_text=raw_text,
            clean_text=clean_text,
            footnotes=footnotes
        )
        result.verses.append(verse)

    if result.verses:
        result.books_parsed = 1
        logger.info(f"Parsed {len(result.verses)} verses from {book_name} {chapter}")

    return result


def parse_html_directory(dirpath: Path | str, pattern: str = "*.htm") -> ParseResult:
    """
    Parse all HTML Bible chapter files in a directory.

    Skips chapter 00 files (introductions) and files without chapter numbers.

    Args:
        dirpath: Path to directory containing HTML files
        pattern: Glob pattern for HTML files (default: "*.htm")

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

    # Find all HTML files
    html_files = sorted(dirpath.glob(pattern))
    if not html_files:
        result.errors.append(f"No HTML files found in {dirpath} matching {pattern}")
        return result

    # Filter to only valid chapter files (skip 00, skip files without chapter numbers)
    valid_files = []
    for html_file in html_files:
        extracted = extract_book_chapter_from_filename(html_file.name)
        if extracted:
            usfm_code, chapter = extracted
            if chapter > 0:  # Skip chapter 00 (introductions)
                valid_files.append(html_file)

    if not valid_files:
        result.errors.append(f"No valid chapter files found in {dirpath} (files must match pattern like MAT01.htm)")
        return result

    logger.info(f"Found {len(valid_files)} HTML chapter files in {dirpath}")

    for html_file in valid_files:
        logger.info(f"Processing: {html_file.name}")
        file_result = parse_html_file(html_file)
        result.verses.extend(file_result.verses)
        result.books_parsed += file_result.books_parsed
        result.errors.extend(file_result.errors)

    logger.info(f"Total: {result.verse_count} verses from {result.books_parsed} chapters")
    return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python html_parser.py <html_file_or_directory>")
        print("\nExamples:")
        print("  python html_parser.py data/bibles/bgt_html/MAT01.htm")
        print("  python html_parser.py data/bibles/bgt_html/")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file():
        result = parse_html_file(path)
    elif path.is_dir():
        result = parse_html_directory(path)
    else:
        print(f"Path not found: {path}")
        sys.exit(1)

    print(f"\nParsing Results:")
    print(f"  Chapters parsed: {result.books_parsed}")
    print(f"  Verses extracted: {result.verse_count}")
    print(f"  Errors: {len(result.errors)}")

    if result.errors:
        print("\nErrors:")
        for error in result.errors[:10]:
            print(f"  - {error}")

    if result.verses:
        print(f"\nFirst 3 verses:")
        for verse in result.verses[:3]:
            print(f"  {verse.book_name} {verse.chapter}:{verse.verse}")
            text_preview = verse.clean_text[:80] + "..." if len(verse.clean_text) > 80 else verse.clean_text
            print(f"    {text_preview}")
            if verse.footnotes:
                print(f"    Footnotes: {len(verse.footnotes)}")
