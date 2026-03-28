"""
Shared Tool Registry for NLM.

Single source of truth for tool definitions used by both:
- MCP server (mcp_server/server.py) via FastMCP wrappers
- In-app chat endpoint (routes/chat.py) via Anthropic tool-use format

Tool functions live in mcp_server/tools/. This registry:
1. Imports those functions
2. Defines Anthropic-format JSON schemas for each tool
3. Provides get_tools() to retrieve schemas (with readonly filtering)
4. Provides call_tool() to dispatch tool calls by name
"""

from typing import Any

# Import tool functions from MCP tools (the single source of truth)
from mcp_server.tools.language import list_languages, get_language_info
from mcp_server.tools.bible import (
    list_bible_books,
    get_chapter,
    get_bible_chunk,
    get_parallel_verses,
    # save_bible_batches excluded — file-writing tool, not useful for chat
)
from mcp_server.tools.dictionary import (
    list_dictionary_entries,
    get_dictionary_entry,
    upsert_dictionary_entries,
)
from mcp_server.tools.grammar import (
    list_grammar_categories,
    get_grammar_category,
    update_grammar_category,
)
from mcp_server.tools.word_index import (
    get_word_index,
    get_words_not_in_dictionary,
    get_word_frequency_list,
)
from mcp_server.tools.memories import (
    list_language_notes,
    search_language_notes,
    list_correction_log,
    search_correction_log,
)


# Async stub for propose_verse_translation.
# write tool is short-circuited before call_tool in run_tool_loop.
# Must be awaitable for any theoretical edge-case resume paths.
async def _propose_verse_translation_stub(db, **kwargs):
    return kwargs


# =============================================================================
# Tool Metadata: Static Anthropic-format schemas
# =============================================================================
# These are hand-written (not auto-generated) for reliability.
# When adding a new MCP tool, add a corresponding entry here.

_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # --- Language Tools ---
    {
        "name": "list_languages",
        "description": "Get all languages with translation progress stats. Returns list of languages with codes, names, status, and progress for human and AI translations.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "readonly": True,
    },
    {
        "name": "get_language_info",
        "description": "Get detailed info for a specific language including translation levels and metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'english', 'heb', 'bughotu')",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    # --- Bible Tools ---
    {
        "name": "list_bible_books",
        "description": "Get all Bible books for a language, sorted by canonical order (1-66) with chapter counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'english', 'heb')",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    {
        "name": "get_chapter",
        "description": "Get all verses for a Bible chapter. Returns verses with text and human_verified status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'english', 'heb')",
                },
                "book_code": {
                    "type": "string",
                    "description": "Book code (e.g., 'genesis', '1_chronicles')",
                },
                "chapter": {
                    "type": "integer",
                    "description": "Chapter number (1-indexed)",
                },
            },
            "required": ["language_code", "book_code", "chapter"],
        },
        "readonly": True,
    },
    {
        "name": "get_bible_chunk",
        "description": "Get paginated Bible verses for large text processing. Returns verses with pagination info (total, offset, limit).",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'english', 'heb')",
                },
                "book_code": {
                    "type": "string",
                    "description": "Optional book filter (e.g., 'genesis')",
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of verses to skip (default 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum verses to return (default 100, max 500)",
                },
                # save_to_file intentionally excluded — not useful in chat context
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    {
        "name": "get_parallel_verses",
        "description": "Fetch the same verses across multiple languages for side-by-side comparison. When both human and AI translations exist, human is preferred.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Languages to compare (2-10, e.g., ['english', 'bughotu'])",
                },
                "book_code": {
                    "type": "string",
                    "description": "Book code (e.g., 'genesis', 'john')",
                },
                "chapter": {
                    "type": "integer",
                    "description": "Chapter number (1-indexed)",
                },
                "verse_start": {
                    "type": "integer",
                    "description": "Starting verse (default: 1)",
                },
                "verse_end": {
                    "type": "integer",
                    "description": "Ending verse (default: all in chapter)",
                },
                # save_to_file intentionally excluded
            },
            "required": ["language_codes", "book_code", "chapter"],
        },
        "readonly": True,
    },
    # --- Dictionary Tools ---
    {
        "name": "list_dictionary_entries",
        "description": "Get paginated dictionary entries for a language. Supports search by word and definition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of entries to skip (default 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum entries to return (default 100)",
                },
                "search": {
                    "type": "string",
                    "description": "Optional search term (searches word and definition)",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    {
        "name": "get_dictionary_entry",
        "description": "Get a specific dictionary entry by word (exact match). Returns definition, part of speech, and examples.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
                "word": {
                    "type": "string",
                    "description": "Word to look up (exact match)",
                },
            },
            "required": ["language_code", "word"],
        },
        "readonly": True,
    },
    {
        "name": "upsert_dictionary_entries",
        "description": "Insert or update dictionary entries. Each entry must have: word, definition, part_of_speech (optional: examples).",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Target language code",
                },
                "entries": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of entries with word, definition, part_of_speech",
                },
            },
            "required": ["language_code", "entries"],
        },
        "readonly": False,
    },
    # --- Grammar Tools ---
    {
        "name": "list_grammar_categories",
        "description": "List all 5 grammar categories (phonology, morphology, syntax, semantics, discourse) with content status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    {
        "name": "get_grammar_category",
        "description": "Get specific grammar category content including description, subcategories, notes, and examples.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
                "category": {
                    "type": "string",
                    "enum": ["phonology", "morphology", "syntax", "semantics", "discourse"],
                    "description": "Grammar category name",
                },
            },
            "required": ["language_code", "category"],
        },
        "readonly": True,
    },
    {
        "name": "update_grammar_category",
        "description": "Update grammar category content (description, subcategories, notes, examples).",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Target language code",
                },
                "category": {
                    "type": "string",
                    "enum": ["phonology", "morphology", "syntax", "semantics", "discourse"],
                    "description": "Grammar category name",
                },
                "content": {
                    "type": "object",
                    "description": "Fields to update (description, subcategories, notes, examples)",
                },
            },
            "required": ["language_code", "category", "content"],
        },
        "readonly": False,
    },
    # --- Word Index Tools ---
    {
        "name": "get_word_index",
        "description": "Look up a word in the word index. Returns occurrence count, book/chapter distribution, in_dictionary status, and verse locations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'bughotu', 'english')",
                },
                "word": {
                    "type": "string",
                    "description": "Word to look up (case-insensitive)",
                },
                "include_occurrences": {
                    "type": "boolean",
                    "description": "Whether to include occurrence details (default true)",
                },
                "max_occurrences": {
                    "type": "integer",
                    "description": "Max occurrences to return (default 50)",
                },
            },
            "required": ["language_code", "word"],
        },
        "readonly": True,
    },
    {
        "name": "get_words_not_in_dictionary",
        "description": "Find words appearing frequently in the corpus but missing from the dictionary. Useful for prioritizing dictionary work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code",
                },
                "min_frequency": {
                    "type": "integer",
                    "description": "Minimum occurrence count to include (default 3)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default 100)",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    {
        "name": "get_word_frequency_list",
        "description": "Get the top N most frequent words in the corpus, sorted by frequency descending.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of words to return (default 500)",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    # --- Memories Tools ---
    {
        "name": "list_language_notes",
        "description": "List all notes for a language, sorted by most recently modified. Use for quick recall of saved observations about a language.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max notes to return (default 50, max 100)",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    {
        "name": "search_language_notes",
        "description": "Search notes for a language by phrase (case-insensitive substring match). Returns matching notes sorted by most recently modified.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
                "search_term": {
                    "type": "string",
                    "description": "Phrase to search for in note text (empty string returns all notes)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max notes to return (default 50, max 100)",
                },
            },
            "required": ["language_code", "search_term"],
        },
        "readonly": True,
    },
    {
        "name": "list_correction_log",
        "description": "List correction log entries for a language with optional content_type filtering and pagination. Sorted by most recently created.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["bible_verse", "dictionary_entry", "grammar_category"],
                    "description": "Optional filter by content type",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number, 1-indexed (default 1)",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Entries per page (default 50, max 100)",
                },
            },
            "required": ["language_code"],
        },
        "readonly": True,
    },
    {
        "name": "search_correction_log",
        "description": "Search correction log entries across original_text, what_was_wrong, and correction fields (case-insensitive). Optionally filter by content_type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language_code": {
                    "type": "string",
                    "description": "Language code (e.g., 'heb', 'bughotu')",
                },
                "search_term": {
                    "type": "string",
                    "description": "Phrase to search across all three text fields (empty string returns all entries)",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["bible_verse", "dictionary_entry", "grammar_category"],
                    "description": "Optional filter by content type",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default 50, max 100)",
                },
            },
            "required": ["language_code", "search_term"],
        },
        "readonly": True,
    },
    # --- Translation-only tools (excluded from general chat by translation_only=True) ---
    {
        "name": "propose_verse_translation",
        "description": "Submit your completed translation for this verse. Call this when you have gathered sufficient context and are confident. This presents the translation to the human for review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "translated_text": {
                    "type": "string",
                    "description": "The complete translated verse text in the target language",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0.0 (uncertain) to 1.0 (very confident)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Brief explanation of key translation decisions (1-3 sentences)",
                },
                "verse_number": {
                    "type": "integer",
                    "description": "The verse number being proposed. Required — used for frontend routing in both batch and chat modes.",
                },
            },
            "required": ["translated_text", "confidence", "rationale", "verse_number"],
        },
        "readonly": False,
        "translation_only": True,  # Excluded from general chat tool list
    },
]

# Map tool names to their implementation functions
_TOOL_FUNCTIONS: dict[str, Any] = {
    "list_languages": list_languages,
    "get_language_info": get_language_info,
    "list_bible_books": list_bible_books,
    "get_chapter": get_chapter,
    "get_bible_chunk": get_bible_chunk,
    "get_parallel_verses": get_parallel_verses,
    "list_dictionary_entries": list_dictionary_entries,
    "get_dictionary_entry": get_dictionary_entry,
    "upsert_dictionary_entries": upsert_dictionary_entries,
    "list_grammar_categories": list_grammar_categories,
    "get_grammar_category": get_grammar_category,
    "update_grammar_category": update_grammar_category,
    "get_word_index": get_word_index,
    "get_words_not_in_dictionary": get_words_not_in_dictionary,
    "get_word_frequency_list": get_word_frequency_list,
    "list_language_notes": list_language_notes,
    "search_language_notes": search_language_notes,
    "list_correction_log": list_correction_log,
    "search_correction_log": search_correction_log,
    "propose_verse_translation": _propose_verse_translation_stub,
}


# =============================================================================
# Public API
# =============================================================================


def get_tools(readonly: bool = True, translation_only: bool = False) -> list[dict[str, Any]]:
    """
    Get tool definitions in Anthropic tool-use format.

    Args:
        readonly: If True (default), exclude write tools (upsert_dictionary, update_grammar).
                  If False, include all tools.
        translation_only: If True, include tools flagged translation_only=True.
                         If False (default), exclude them — keeps chat tool set unaffected.

    Returns:
        List of tool dicts with name, description, input_schema (no 'readonly' key).
    """
    tools = []
    for tool_def in _TOOL_DEFINITIONS:
        if readonly and not tool_def.get("readonly", True):
            continue
        if tool_def.get("translation_only", False) and not translation_only:
            continue
        # Return clean Anthropic format (strip our internal metadata flags)
        tools.append({
            "name": tool_def["name"],
            "description": tool_def["description"],
            "input_schema": tool_def["input_schema"],
        })
    return tools


async def call_tool(name: str, args: dict[str, Any], db) -> dict[str, Any]:
    """
    Dispatch a tool call by name.

    Args:
        name: Tool name (must match a key in _TOOL_FUNCTIONS)
        args: Tool arguments (passed as kwargs to the function, after db)
        db: MongoDBConnector instance

    Returns:
        Tool result dict

    Raises:
        ValueError: If tool name is not registered
    """
    func = _TOOL_FUNCTIONS.get(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name}. Available: {list(_TOOL_FUNCTIONS.keys())}")

    # Strip save_to_file from args if present (chat doesn't write files)
    args = {k: v for k, v in args.items() if k != "save_to_file"}

    return await func(db, **args)


def is_write_tool(name: str) -> bool:
    """Check if a tool modifies data (requires UI confirmation in chat)."""
    for tool_def in _TOOL_DEFINITIONS:
        if tool_def["name"] == name:
            return not tool_def.get("readonly", True)
    return False


def get_tool_names(readonly: bool = True) -> list[str]:
    """Get list of available tool names."""
    return [t["name"] for t in get_tools(readonly=readonly)]
