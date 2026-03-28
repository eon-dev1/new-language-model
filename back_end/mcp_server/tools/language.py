"""
Language tools for MCP server.

Tools:
- list_languages: Get all languages with progress stats
- get_language_info: Detailed info for one language
"""

from typing import Any

from mcp_server.tools.base import (
    ToolError,
    error_response,
    success_response,
    validate_language,
)


async def list_languages(db) -> dict[str, Any]:
    """
    Get all languages with progress stats.

    Args:
        db: MongoDBConnector instance

    Returns:
        {
            "languages": [{code, name, status, is_base_language, translation_stats}],
            "count": int
        }
    """
    languages_coll = db.get_collection("languages")
    cursor = languages_coll.find({})
    docs = await cursor.to_list(length=None)

    languages = []
    for doc in docs:
        languages.append(
            {
                "code": doc["language_code"],
                "name": doc["language_name"],
                "status": doc.get("status", "active"),
                "is_base_language": doc.get("is_base_language", False),
                "translation_stats": doc.get("translation_stats", {}),
            }
        )

    return success_response({"languages": languages, "count": len(languages)})


async def get_language_info(db, language_code: str) -> dict[str, Any]:
    """
    Get detailed info for one language.

    Args:
        db: MongoDBConnector instance
        language_code: The language code to look up

    Returns:
        Full language document (without _id) or error response
    """
    try:
        doc = await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Remove MongoDB _id from response
    result = {k: v for k, v in doc.items() if k != "_id"}

    return result
