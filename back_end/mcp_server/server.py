"""
NLM Database MCP Server

Exposes MongoDB collections to Claude Code/Desktop for AI-assisted
dictionary generation, grammar analysis, and translation verification.

Run with: python -m mcp_server.server
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from db_connector.connection import MongoDBConnector
from shared.logging_setup import install_logging

install_logging()

# Import tool functions
from mcp_server.tools.language import list_languages as _list_languages
from mcp_server.tools.language import get_language_info as _get_language_info
from mcp_server.tools.bible import list_bible_books as _list_bible_books
from mcp_server.tools.bible import get_chapter as _get_chapter
from mcp_server.tools.bible import get_bible_chunk as _get_bible_chunk
from mcp_server.tools.bible import save_bible_batches as _save_bible_batches
from mcp_server.tools.bible import get_parallel_verses as _get_parallel_verses
from mcp_server.tools.dictionary import list_dictionary_entries as _list_dictionary_entries
from mcp_server.tools.dictionary import get_dictionary_entry as _get_dictionary_entry
from mcp_server.tools.dictionary import upsert_dictionary_entries as _upsert_dictionary_entries
from mcp_server.tools.grammar import list_grammar_categories as _list_grammar_categories
from mcp_server.tools.grammar import get_grammar_category as _get_grammar_category
from mcp_server.tools.grammar import update_grammar_category as _update_grammar_category
from mcp_server.tools.word_index import get_word_index as _get_word_index
from mcp_server.tools.word_index import get_words_not_in_dictionary as _get_words_not_in_dictionary
from mcp_server.tools.word_index import get_word_frequency_list as _get_word_frequency_list
from mcp_server.tools.phrase_index import get_phrase_context as _get_phrase_context
from mcp_server.tools.memories import list_language_notes as _list_language_notes
from mcp_server.tools.memories import search_language_notes as _search_language_notes
from mcp_server.tools.memories import list_correction_log as _list_correction_log
from mcp_server.tools.memories import search_correction_log as _search_correction_log


# Initialize MCP server
mcp = FastMCP("nlm-database")

# Global database connector (initialized on first use)
_db: MongoDBConnector | None = None


async def get_db() -> MongoDBConnector:
    """Get database connector, initializing if needed."""
    global _db
    if _db is None:
        connector = MongoDBConnector()
        await connector.connect()
        _db = connector
    return _db


# =============================================================================
# Language Tools
# =============================================================================


@mcp.tool()
async def list_languages() -> dict[str, Any]:
    """
    Get all languages with translation progress stats.

    Returns list of languages with their codes, names, status,
    and progress information for human and AI translations.
    """
    db = await get_db()
    return await _list_languages(db)


@mcp.tool()
async def get_language_info(language_code: str) -> dict[str, Any]:
    """
    Get detailed info for a specific language.

    Args:
        language_code: Language code (e.g., 'english', 'heb', 'kope')

    Returns full language document including translation levels and metadata.
    """
    db = await get_db()
    return await _get_language_info(db, language_code)


# =============================================================================
# Bible Tools
# =============================================================================


@mcp.tool()
async def list_bible_books(language_code: str) -> dict[str, Any]:
    """
    Get all Bible books for a language.

    Args:
        language_code: Language code (e.g., 'english', 'heb')

    Returns books sorted by canonical order (1-66) with chapter counts.
    """
    db = await get_db()
    return await _list_bible_books(db, language_code)


@mcp.tool()
async def get_chapter(
    language_code: str,
    book_code: str,
    chapter: int,
) -> dict[str, Any]:
    """
    Get all verses for a Bible chapter.

    Args:
        language_code: Language code (e.g., 'english', 'heb')
        book_code: Book code (e.g., 'genesis', '1_chronicles')
        chapter: Chapter number (1-indexed)

    Returns verses with text and human_verified status (non-English only).
    """
    db = await get_db()
    return await _get_chapter(db, language_code, book_code, chapter)


@mcp.tool()
async def get_bible_chunk(
    language_code: str,
    book_code: str | None = None,
    offset: int = 0,
    limit: int = 100,
    save_to_file: str | None = None,
) -> dict[str, Any]:
    """
    Get paginated Bible verses for large text processing.

    Args:
        language_code: Language code (e.g., 'english', 'heb')
        book_code: Optional book filter (e.g., 'genesis')
        offset: Number of verses to skip (default 0)
        limit: Maximum verses to return (default 100, max 500)
        save_to_file: Optional filename to save results to temp_files/ directory.
                      Use alphanumeric, underscore, hyphen only (e.g., 'bughotu_batch1').
                      If provided, returns {saved_to, record_count} instead of full data.

    Returns verses with pagination info (total, offset, limit).
    Or if save_to_file: {"saved_to": path, "record_count": N, "filename": str}
    """
    db = await get_db()
    return await _get_bible_chunk(
        db, language_code, book_code, offset, limit, save_to_file
    )


@mcp.tool()
async def save_bible_batches(
    language_code: str,
    batch_size: int = 500,
    batch_start: int = 1,
    batch_end: int | None = None,
    book_code: str | None = None,
    filename_prefix: str | None = None,
) -> dict[str, Any]:
    """
    Save multiple batches of Bible verses to files in a single tool call.

    Solves the "N batches = N approvals" problem - one approval saves any number of batches.

    Args:
        language_code: Language to export (e.g., 'bughotu', 'english')
        batch_size: Verses per batch (1-500, default 500)
        batch_start: First batch number, 1-indexed (default 1)
        batch_end: Last batch number inclusive (None = all remaining batches)
        book_code: Optional book filter (e.g., 'genesis')
        filename_prefix: Prefix for files (default: '{lang}_batch')

    Returns:
        {
            "batches_saved": number of files created,
            "files": [{batch, filename, saved_to, record_count}],
            "verses_saved": total verses across all files,
            "first_batch": starting batch number,
            "last_batch": ending batch number,
            "total_batches_available": total batches for this query
        }

    Examples:
        save_bible_batches("bughotu")  # Save all batches
        save_bible_batches("bughotu", batch_start=5, batch_end=10)  # Save batches 5-10
        save_bible_batches("english", batch_size=250, filename_prefix="eng_export")
    """
    db = await get_db()
    return await _save_bible_batches(
        db, language_code, batch_size, batch_start, batch_end,
        book_code, filename_prefix
    )


@mcp.tool()
async def get_parallel_verses(
    language_codes: list[str],
    book_code: str,
    chapter: int,
    verse_start: int | None = None,
    verse_end: int | None = None,
    save_to_file: str | None = None,
) -> dict[str, Any]:
    """
    Fetch the same verses across multiple languages for side-by-side comparison.

    Args:
        language_codes: Languages to compare (2-10 unique languages, e.g., ['english', 'bughotu'])
        book_code: Book code (e.g., 'genesis', 'john')
        chapter: Chapter number (1-indexed)
        verse_start: Starting verse (default: 1)
        verse_end: Ending verse (default: all in chapter)
        save_to_file: Optional filename to save results to temp_files/ directory
                      (required for responses > 200 verses)

    Returns:
        {
            "parallel_verses": [{book_code, chapter, verse, translations: {lang: {text, human_verified?}}}],
            "languages": list of language codes,
            "book_code": str,
            "chapter": int,
            "verse_range": [start, end],
            "count": number of verses,
            "missing_translations": {lang: [verse_nums]} for languages with gaps
        }

    Notes:
        - When both human and AI translations exist, human is preferred
        - human_verified field only appears for non-English languages
        - Use save_to_file for chapters with >200 verses

    Examples:
        get_parallel_verses(["english", "bughotu"], "genesis", 1)
        get_parallel_verses(["english", "heb", "bughotu"], "john", 3, verse_start=16, verse_end=21)
    """
    db = await get_db()
    return await _get_parallel_verses(
        db, language_codes, book_code, chapter,
        verse_start, verse_end, save_to_file
    )


# =============================================================================
# Dictionary Tools
# =============================================================================


@mcp.tool()
async def list_dictionary_entries(
    language_code: str,
    offset: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    """
    Get paginated dictionary entries for a language.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')
        offset: Number of entries to skip (default 0)
        limit: Maximum entries to return (default 100)
        search: Optional search term (searches word and definition)

    Returns entries with pagination info.
    """
    db = await get_db()
    return await _list_dictionary_entries(db, language_code, offset, limit, search)


@mcp.tool()
async def get_dictionary_entry(
    language_code: str,
    word: str,
) -> dict[str, Any]:
    """
    Get a specific dictionary entry by word.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')
        word: Word to look up (exact match)

    Returns entry with definition, part of speech, and examples.
    """
    db = await get_db()
    return await _get_dictionary_entry(db, language_code, word)


@mcp.tool()
async def upsert_dictionary_entries(
    language_code: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Insert or update dictionary entries.

    Args:
        language_code: Target language code
        entries: List of entry dicts with word, definition, part_of_speech

    Returns counts of created and updated entries.
    Each entry must have: word, definition, part_of_speech (optional: examples)
    """
    db = await get_db()
    return await _upsert_dictionary_entries(db, language_code, entries)


# =============================================================================
# Grammar Tools
# =============================================================================


@mcp.tool()
async def list_grammar_categories(language_code: str) -> dict[str, Any]:
    """
    List all grammar categories with content status.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')

    Returns 5 categories: phonology, morphology, syntax, semantics, discourse.
    Each shows has_content boolean indicating if populated.
    """
    db = await get_db()
    return await _list_grammar_categories(db, language_code)


@mcp.tool()
async def get_grammar_category(
    language_code: str,
    category: str,
) -> dict[str, Any]:
    """
    Get specific grammar category content.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')
        category: Category name (phonology, morphology, syntax, semantics, discourse)

    Returns category with description, subcategories, notes, and examples.
    """
    db = await get_db()
    return await _get_grammar_category(db, language_code, category)


@mcp.tool()
async def update_grammar_category(
    language_code: str,
    category: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """
    Update grammar category content.

    Args:
        language_code: Target language code
        category: Category name (phonology, morphology, syntax, semantics, discourse)
        content: Fields to update (description, subcategories, notes, examples)

    Returns success status and timestamp.
    """
    db = await get_db()
    return await _update_grammar_category(db, language_code, category, content)


# =============================================================================
# Word Index Tools
# =============================================================================


@mcp.tool()
async def get_word_index(
    language_code: str,
    word: str,
    include_occurrences: bool = True,
    max_occurrences: int = 50,
) -> dict[str, Any]:
    """
    Look up a word in the word index.

    Args:
        language_code: Language code (e.g., 'bughotu')
        word: Word to look up (case-insensitive)
        include_occurrences: Whether to include occurrence details (default True)
        max_occurrences: Max occurrences to return (default 50)

    Returns word statistics: total_count, book_count, chapter_count,
    in_dictionary flag, first_seen location, and occurrence details.
    """
    db = await get_db()
    return await _get_word_index(
        db, language_code, word, include_occurrences, max_occurrences
    )


@mcp.tool()
async def get_words_not_in_dictionary(
    language_code: str,
    min_frequency: int = 3,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Find words appearing frequently in the corpus but missing from the dictionary.

    Args:
        language_code: Language code
        min_frequency: Minimum occurrence count to include (default 3)
        limit: Maximum results to return (default 100)

    Returns list of words sorted by frequency (descending), with counts.
    Useful for prioritizing dictionary work.
    """
    db = await get_db()
    return await _get_words_not_in_dictionary(db, language_code, min_frequency, limit)


@mcp.tool()
async def get_word_frequency_list(
    language_code: str,
    top_n: int = 500,
) -> dict[str, Any]:
    """
    Get the top N most frequent words in the corpus.

    Args:
        language_code: Language code
        top_n: Number of words to return (default 500)

    Returns list of words sorted by frequency (descending) with counts
    and in_dictionary status.
    """
    db = await get_db()
    return await _get_word_frequency_list(db, language_code, top_n)


# =============================================================================
# Phrase Index Tool
# =============================================================================


@mcp.tool()
async def get_phrase_context(
    language_code: str,
    text: str,
    location_text_language: str | None = None,
    book_code: str | None = None,
    chapter: int | None = None,
    verse: int | None = None,
    min_word_df_max: int = 200,
    max_locations_per_phrase: int = 10,
) -> dict[str, Any]:
    """
    Find recurring distinctive 4-grams in `text` and where else they appear.

    Two use cases:
      (a) Cross-lingual reuse: pass English text with language_code="english"
          and location_text_language="<target>" — get English 4-grams with
          verified target translations at other locations.
      (b) Intra-target consistency: pass a target-language draft with
          language_code="<target>" and default location_text_language.

    Args:
        language_code: Language of `text`; selects which phrase_index to query
        text: Text to scan (max 50K chars)
        location_text_language: Language to fetch location text in
            (defaults to language_code)
        book_code, chapter, verse: Optional self-reference exclusion
            (all-or-nothing)
        min_word_df_max: Scaffolding filter — keep only phrases whose rarest
            token appears in <= N verses (default 200)
        max_locations_per_phrase: Cap locations per phrase (default 10)

    Returns phrases ordered by min_word_df asc, df desc. Empty is a normal
    result.
    """
    db = await get_db()
    return await _get_phrase_context(
        db, language_code, text, location_text_language,
        book_code, chapter, verse, min_word_df_max, max_locations_per_phrase,
    )


# =============================================================================
# Memories Tools
# =============================================================================


@mcp.tool()
async def list_language_notes(
    language_code: str,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List all notes for a language, sorted by most recently modified.

    Args:
        language_code: Language code (e.g., 'heb', 'bughotu')
        limit: Max notes to return (default 50, max 100)

    Returns notes with id, text, created_at, updated_at, plus count and total.
    """
    db = await get_db()
    return await _list_language_notes(db, language_code, limit)


@mcp.tool()
async def search_language_notes(
    language_code: str,
    search_term: str,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Search notes for a language by phrase (case-insensitive substring match).

    Args:
        language_code: Language code (e.g., 'heb', 'bughotu')
        search_term: Phrase to search for (empty string returns all notes)
        limit: Max notes to return (default 50, max 100)

    Returns matching notes sorted by most recently modified.
    """
    db = await get_db()
    return await _search_language_notes(db, language_code, search_term, limit)


@mcp.tool()
async def list_correction_log(
    language_code: str,
    content_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """
    List correction log entries for a language with optional filtering and pagination.

    Args:
        language_code: Language code (e.g., 'heb', 'bughotu')
        content_type: Optional filter (bible_verse | dictionary_entry | grammar_category)
        page: Page number, 1-indexed (default 1)
        page_size: Entries per page (default 50, max 100)

    Returns entries sorted by created_at DESC with pagination metadata.
    """
    db = await get_db()
    return await _list_correction_log(db, language_code, content_type, page, page_size)


@mcp.tool()
async def search_correction_log(
    language_code: str,
    search_term: str,
    content_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Search correction log entries across original_text, what_was_wrong, and correction fields.

    Args:
        language_code: Language code (e.g., 'heb', 'bughotu')
        search_term: Phrase to search across all text fields (empty string returns all)
        content_type: Optional filter (bible_verse | dictionary_entry | grammar_category)
        limit: Max entries to return (default 50, max 100)

    Returns matching entries sorted by created_at DESC.
    """
    db = await get_db()
    return await _search_correction_log(db, language_code, search_term, content_type, limit)


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    import sys

    # Print to stderr (stdout is reserved for MCP JSON-RPC)
    tool_count = len(mcp._tool_manager._tools)
    print(f"NLM Database MCP Server v0.1.0", file=sys.stderr)
    print(f"Registered {tool_count} tools, waiting for client connection...", file=sys.stderr)
    print(f"(Press Ctrl+C to stop)", file=sys.stderr)

    mcp.run(transport="stdio")
