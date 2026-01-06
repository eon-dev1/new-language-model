# usfm_book_codes.py
"""
USFM 3-letter book code mapping to MongoDB book codes.

Maps standard USFM book identifiers (e.g., GEN, MAT) to the internal
MongoDB book_code format (e.g., genesis, matthew) used in the NLM database.
"""

from typing import Optional

# USFM 3-letter codes to MongoDB book_code mapping
# Format: USFM_CODE -> (book_code, display_name)
USFM_BOOK_DATA = {
    # Old Testament (39 books)
    "GEN": ("genesis", "Genesis"),
    "EXO": ("exodus", "Exodus"),
    "LEV": ("leviticus", "Leviticus"),
    "NUM": ("numbers", "Numbers"),
    "DEU": ("deuteronomy", "Deuteronomy"),
    "JOS": ("joshua", "Joshua"),
    "JDG": ("judges", "Judges"),
    "RUT": ("ruth", "Ruth"),
    "1SA": ("1_samuel", "1 Samuel"),
    "2SA": ("2_samuel", "2 Samuel"),
    "1KI": ("1_kings", "1 Kings"),
    "2KI": ("2_kings", "2 Kings"),
    "1CH": ("1_chronicles", "1 Chronicles"),
    "2CH": ("2_chronicles", "2 Chronicles"),
    "EZR": ("ezra", "Ezra"),
    "NEH": ("nehemiah", "Nehemiah"),
    "EST": ("esther", "Esther"),
    "JOB": ("job", "Job"),
    "PSA": ("psalms", "Psalms"),
    "PRO": ("proverbs", "Proverbs"),
    "ECC": ("ecclesiastes", "Ecclesiastes"),
    "SNG": ("song_of_solomon", "Song of Solomon"),
    "ISA": ("isaiah", "Isaiah"),
    "JER": ("jeremiah", "Jeremiah"),
    "LAM": ("lamentations", "Lamentations"),
    "EZK": ("ezekiel", "Ezekiel"),
    "DAN": ("daniel", "Daniel"),
    "HOS": ("hosea", "Hosea"),
    "JOL": ("joel", "Joel"),
    "AMO": ("amos", "Amos"),
    "OBA": ("obadiah", "Obadiah"),
    "JON": ("jonah", "Jonah"),
    "MIC": ("micah", "Micah"),
    "NAM": ("nahum", "Nahum"),
    "HAB": ("habakkuk", "Habakkuk"),
    "ZEP": ("zephaniah", "Zephaniah"),
    "HAG": ("haggai", "Haggai"),
    "ZEC": ("zechariah", "Zechariah"),
    "MAL": ("malachi", "Malachi"),
    # New Testament (27 books)
    "MAT": ("matthew", "Matthew"),
    "MRK": ("mark", "Mark"),
    "LUK": ("luke", "Luke"),
    "JHN": ("john", "John"),
    "ACT": ("acts", "Acts"),
    "ROM": ("romans", "Romans"),
    "1CO": ("1_corinthians", "1 Corinthians"),
    "2CO": ("2_corinthians", "2 Corinthians"),
    "GAL": ("galatians", "Galatians"),
    "EPH": ("ephesians", "Ephesians"),
    "PHP": ("philippians", "Philippians"),
    "COL": ("colossians", "Colossians"),
    "1TH": ("1_thessalonians", "1 Thessalonians"),
    "2TH": ("2_thessalonians", "2 Thessalonians"),
    "1TI": ("1_timothy", "1 Timothy"),
    "2TI": ("2_timothy", "2 Timothy"),
    "TIT": ("titus", "Titus"),
    "PHM": ("philemon", "Philemon"),
    "HEB": ("hebrews", "Hebrews"),
    "JAS": ("james", "James"),
    "1PE": ("1_peter", "1 Peter"),
    "2PE": ("2_peter", "2 Peter"),
    "1JN": ("1_john", "1 John"),
    "2JN": ("2_john", "2 John"),
    "3JN": ("3_john", "3 John"),
    "JUD": ("jude", "Jude"),
    "REV": ("revelation", "Revelation"),
}

# Derived mappings for quick lookups
USFM_TO_BOOK_CODE = {code: data[0] for code, data in USFM_BOOK_DATA.items()}
USFM_TO_BOOK_NAME = {code: data[1] for code, data in USFM_BOOK_DATA.items()}
BOOK_CODE_TO_USFM = {data[0]: code for code, data in USFM_BOOK_DATA.items()}
BOOK_NAME_TO_USFM = {data[1]: code for code, data in USFM_BOOK_DATA.items()}


def usfm_code_to_book_code(usfm_code: str) -> Optional[str]:
    """
    Convert USFM 3-letter code to MongoDB book_code.

    Args:
        usfm_code: USFM book identifier (e.g., "GEN", "MAT")

    Returns:
        MongoDB book_code (e.g., "genesis", "matthew") or None if not found
    """
    return USFM_TO_BOOK_CODE.get(usfm_code.upper())


def usfm_code_to_book_name(usfm_code: str) -> Optional[str]:
    """
    Convert USFM 3-letter code to display book name.

    Args:
        usfm_code: USFM book identifier (e.g., "GEN", "MAT")

    Returns:
        Display name (e.g., "Genesis", "Matthew") or None if not found
    """
    return USFM_TO_BOOK_NAME.get(usfm_code.upper())


def book_code_to_usfm_code(book_code: str) -> Optional[str]:
    """
    Convert MongoDB book_code to USFM 3-letter code.

    Args:
        book_code: MongoDB book code (e.g., "genesis", "matthew")

    Returns:
        USFM code (e.g., "GEN", "MAT") or None if not found
    """
    return BOOK_CODE_TO_USFM.get(book_code.lower())


def book_name_to_book_code(book_name: str) -> Optional[str]:
    """
    Convert display book name to MongoDB book_code.

    Args:
        book_name: Display name (e.g., "Genesis", "1 Samuel")

    Returns:
        MongoDB book_code (e.g., "genesis", "1_samuel") or None if not found
    """
    usfm_code = BOOK_NAME_TO_USFM.get(book_name)
    if usfm_code:
        return USFM_TO_BOOK_CODE.get(usfm_code)
    return None


def is_valid_usfm_code(usfm_code: str) -> bool:
    """Check if a USFM code is valid."""
    return usfm_code.upper() in USFM_BOOK_DATA


def get_all_usfm_codes() -> list[str]:
    """Get all valid USFM book codes in canonical order."""
    return list(USFM_BOOK_DATA.keys())


def get_all_book_codes() -> list[str]:
    """Get all MongoDB book codes in canonical order."""
    return [data[0] for data in USFM_BOOK_DATA.values()]


if __name__ == "__main__":
    # Quick test
    print("USFM Book Code Mapping Test")
    print("-" * 40)

    test_codes = ["GEN", "1SA", "MAT", "REV", "INVALID"]
    for code in test_codes:
        book_code = usfm_code_to_book_code(code)
        book_name = usfm_code_to_book_name(code)
        print(f"{code} -> book_code: {book_code}, name: {book_name}")

    print(f"\nTotal books: {len(USFM_BOOK_DATA)}")