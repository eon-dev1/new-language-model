"""
Word index tools for MCP server.

Tools:
- get_word_index: Look up a word's occurrences and statistics
- get_words_not_in_dictionary: Find frequent words missing from the dictionary
- get_word_frequency_list: Top N words by frequency
"""

from typing import Any

from constants import Collection
from mcp_server.tools.base import (
    ToolError,
    error_response,
    validate_language,
)


async def get_word_index(
    db,
    language_code: str,
    word: str,
    include_occurrences: bool = True,
    max_occurrences: int = 50,
) -> dict[str, Any]:
    """
    Look up a word in the word index.

    Args:
        db: MongoDBConnector instance
        language_code: Language code (e.g., 'bughotu')
        word: Word to look up (case-insensitive)
        include_occurrences: Whether to include occurrence details (default True)
        max_occurrences: Max occurrences to return (default 50)

    Returns:
        Word statistics and occurrence locations
    """
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    word_index_col = db.get_collection(Collection.WORD_INDEX)
    word_lower = word.lower()

    doc = await word_index_col.find_one({
        "language_code": language_code.lower(),
        "word": word_lower,
    })

    if doc is None:
        return {
            "word": word_lower,
            "language_code": language_code.lower(),
            "total_count": 0,
            "book_count": 0,
            "chapter_count": 0,
            "in_dictionary": False,
            "first_seen": None,
            "occurrences": [],
            "message": "Word not found in index. It may not appear in the corpus, or the index may need rebuilding.",
        }

    result: dict[str, Any] = {
        "word": doc["word"],
        "language_code": doc["language_code"],
        "total_count": doc["total_count"],
        "book_count": doc["book_count"],
        "chapter_count": doc["chapter_count"],
        "in_dictionary": doc["in_dictionary"],
        "first_seen": doc["first_seen"],
    }

    if include_occurrences:
        occurrences = doc.get("occurrences", [])
        result["occurrences"] = occurrences[:max_occurrences]
        result["occurrences_returned"] = min(len(occurrences), max_occurrences)
    else:
        result["occurrences"] = []
        result["occurrences_returned"] = 0

    return result


async def get_words_not_in_dictionary(
    db,
    language_code: str,
    min_frequency: int = 3,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Find words appearing frequently in the corpus but missing from the dictionary.

    Args:
        db: MongoDBConnector instance
        language_code: Language code
        min_frequency: Minimum occurrence count to include (default 3)
        limit: Maximum results to return (default 100)

    Returns:
        List of words sorted by frequency (descending), with counts
    """
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    word_index_col = db.get_collection(Collection.WORD_INDEX)

    query: dict[str, Any] = {
        "language_code": language_code.lower(),
        "in_dictionary": False,
        "total_count": {"$gte": min_frequency},
    }

    cursor = word_index_col.find(
        query,
        {"word": 1, "total_count": 1, "book_count": 1, "first_seen": 1},
    ).sort("total_count", -1).limit(limit)

    words = []
    async for doc in cursor:
        words.append({
            "word": doc["word"],
            "total_count": doc["total_count"],
            "book_count": doc["book_count"],
            "first_seen": doc.get("first_seen"),
        })

    return {
        "language_code": language_code.lower(),
        "min_frequency": min_frequency,
        "words": words,
        "count": len(words),
    }


async def get_word_frequency_list(
    db,
    language_code: str,
    top_n: int = 500,
) -> dict[str, Any]:
    """
    Get the top N most frequent words in the corpus.

    Args:
        db: MongoDBConnector instance
        language_code: Language code
        top_n: Number of words to return (default 500)

    Returns:
        List of words sorted by frequency (descending)
    """
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    word_index_col = db.get_collection(Collection.WORD_INDEX)

    cursor = word_index_col.find(
        {"language_code": language_code.lower()},
        {"word": 1, "total_count": 1, "book_count": 1, "chapter_count": 1, "in_dictionary": 1},
    ).sort("total_count", -1).limit(top_n)

    words = []
    async for doc in cursor:
        words.append({
            "word": doc["word"],
            "total_count": doc["total_count"],
            "book_count": doc["book_count"],
            "chapter_count": doc["chapter_count"],
            "in_dictionary": doc["in_dictionary"],
        })

    return {
        "language_code": language_code.lower(),
        "top_n": top_n,
        "words": words,
        "count": len(words),
    }
