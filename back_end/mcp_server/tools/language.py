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
            "languages": [{code, name, status, is_base_language, progress}],
            "count": int
        }
    """
    languages_coll = db.get_collection("languages")
    cursor = languages_coll.find({})
    docs = await cursor.to_list(length=None)

    languages = []
    for doc in docs:
        # Build progress dict from translation_levels
        progress = {}
        translation_levels = doc.get("translation_levels", {})

        if "human" in translation_levels:
            progress["human"] = translation_levels["human"]

        # AI progress only for non-English languages
        if "ai" in translation_levels and translation_levels["ai"] is not None:
            progress["ai"] = translation_levels["ai"]
        else:
            progress["ai"] = None

        languages.append(
            {
                "code": doc["language_code"],
                "name": doc["language_name"],
                "status": doc.get("status", "active"),
                "is_base_language": doc.get("is_base_language", False),
                "progress": progress,
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
