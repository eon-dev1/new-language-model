"""
NLM Database MCP Server

Exposes MongoDB collections to Claude Code/Desktop for AI-assisted
dictionary generation, grammar analysis, and translation verification.

Run with: python -m mcp_server.server
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from db_connector.connection import MongoDBConnector

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


# Initialize MCP server
mcp = FastMCP("nlm-database")

# Global database connector (initialized on first use)
_db: MongoDBConnector | None = None


async def get_db() -> MongoDBConnector:
    """Get database connector, initializing if needed."""
    global _db
    if _db is None:
        _db = MongoDBConnector()
        await _db.connect()
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
async def list_bible_books(
    language_code: str, translation_type: str | None = None
) -> dict[str, Any]:
    """
    Get all Bible books for a language.

    Args:
        language_code: Language code (e.g., 'english', 'heb')
        translation_type: Optional filter ('human' or 'ai')

    Returns books sorted by canonical order (1-66) with chapter counts.
    """
    db = await get_db()
    return await _list_bible_books(db, language_code, translation_type)


@mcp.tool()
async def get_chapter(
    language_code: str,
    book_code: str,
    chapter: int,
    translation_type: str | None = None,
) -> dict[str, Any]:
    """
    Get all verses for a Bible chapter.

    Args:
        language_code: Language code (e.g., 'english', 'heb')
        book_code: Book code (e.g., 'genesis', '1_chronicles')
        chapter: Chapter number (1-indexed)
        translation_type: Optional filter ('human' or 'ai')

    Returns verses with text and human_verified status (non-English only).
    """
    db = await get_db()
    return await _get_chapter(db, language_code, book_code, chapter, translation_type)


@mcp.tool()
async def get_bible_chunk(
    language_code: str,
    book_code: str | None = None,
    offset: int = 0,
    limit: int = 100,
    translation_type: str | None = None,
    save_to_file: str | None = None,
) -> dict[str, Any]:
    """
    Get paginated Bible verses for large text processing.

    Args:
        language_code: Language code (e.g., 'english', 'heb')
        book_code: Optional book filter (e.g., 'genesis')
        offset: Number of verses to skip (default 0)
        limit: Maximum verses to return (default 100, max 500)
        translation_type: Optional filter ('human' or 'ai')
        save_to_file: Optional filename to save results to temp_files/ directory.
                      Use alphanumeric, underscore, hyphen only (e.g., 'bughotu_batch1').
                      If provided, returns {saved_to, record_count} instead of full data.

    Returns verses with pagination info (total, offset, limit).
    Or if save_to_file: {"saved_to": path, "record_count": N, "filename": str}
    """
    db = await get_db()
    return await _get_bible_chunk(
        db, language_code, book_code, offset, limit, translation_type, save_to_file
    )


@mcp.tool()
async def save_bible_batches(
    language_code: str,
    batch_size: int = 500,
    batch_start: int = 1,
    batch_end: int | None = None,
    book_code: str | None = None,
    translation_type: str | None = None,
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
        translation_type: Optional filter ('human' or 'ai')
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
        book_code, translation_type, filename_prefix
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
            "parallel_verses": [{book_code, chapter, verse, translations: {lang: {text, translation_type, human_verified?}}}],
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
    translation_type: str | None = None,
    offset: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    """
    Get paginated dictionary entries for a language.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')
        translation_type: Optional filter ('human' or 'ai')
        offset: Number of entries to skip (default 0)
        limit: Maximum entries to return (default 100)
        search: Optional search term (searches word and definition)

    Returns entries with pagination info.
    """
    db = await get_db()
    return await _list_dictionary_entries(db, language_code, translation_type, offset, limit, search)


@mcp.tool()
async def get_dictionary_entry(
    language_code: str,
    word: str,
    translation_type: str | None = None,
) -> dict[str, Any]:
    """
    Get a specific dictionary entry by word.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')
        word: Word to look up (exact match)
        translation_type: Optional filter ('human' or 'ai')

    Returns entry with definition, part of speech, and examples.
    """
    db = await get_db()
    return await _get_dictionary_entry(db, language_code, word, translation_type)


@mcp.tool()
async def upsert_dictionary_entries(
    language_code: str,
    translation_type: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Insert or update dictionary entries.

    Args:
        language_code: Target language code
        translation_type: Required ('human' or 'ai')
        entries: List of entry dicts with word, definition, part_of_speech

    Returns counts of created and updated entries.
    Each entry must have: word, definition, part_of_speech (optional: examples)
    """
    db = await get_db()
    return await _upsert_dictionary_entries(db, language_code, translation_type, entries)


# =============================================================================
# Grammar Tools
# =============================================================================


@mcp.tool()
async def list_grammar_categories(
    language_code: str,
    translation_type: str | None = None,
) -> dict[str, Any]:
    """
    List all grammar categories with content status.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')
        translation_type: Optional filter ('human' or 'ai')

    Returns 5 categories: phonology, morphology, syntax, semantics, discourse.
    Each shows has_content boolean indicating if populated.
    """
    db = await get_db()
    return await _list_grammar_categories(db, language_code, translation_type)


@mcp.tool()
async def get_grammar_category(
    language_code: str,
    category: str,
    translation_type: str | None = None,
) -> dict[str, Any]:
    """
    Get specific grammar category content.

    Args:
        language_code: Language code (e.g., 'heb', 'kope')
        category: Category name (phonology, morphology, syntax, semantics, discourse)
        translation_type: Optional filter ('human' or 'ai')

    Returns category with description, subcategories, notes, and examples.
    """
    db = await get_db()
    return await _get_grammar_category(db, language_code, category, translation_type)


@mcp.tool()
async def update_grammar_category(
    language_code: str,
    category: str,
    translation_type: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """
    Update grammar category content.

    Args:
        language_code: Target language code
        category: Category name (phonology, morphology, syntax, semantics, discourse)
        translation_type: Required ('human' or 'ai')
        content: Fields to update (description, subcategories, notes, examples)

    Returns success status and timestamp.
    """
    db = await get_db()
    return await _update_grammar_category(db, language_code, category, translation_type, content)


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
