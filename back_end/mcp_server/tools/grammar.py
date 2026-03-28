"""
Grammar tools for MCP server.

Tools:
- list_grammar_categories: List all 5 categories with content status
- get_grammar_category: Get specific category content
- update_grammar_category: Update category using $set

Note: Grammar uses nested categories{} pattern.
One doc per language with 5 categories:
phonology, morphology, syntax, semantics, discourse
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mcp_server.tools.base import (
    ToolError,
    error_response,
    success_response,
    validate_language,
)


class GrammarUpdateInput(BaseModel):
    """LLM-facing validation model for grammar category updates."""
    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(None, max_length=10000)
    notes: Optional[list[str]] = Field(None, max_length=50)
    examples: Optional[list[str]] = Field(None, max_length=50)
    subcategories: Optional[list[dict]] = Field(None, max_length=30)

# Valid grammar category names
VALID_CATEGORIES = frozenset(
    ["phonology", "morphology", "syntax", "semantics", "discourse"]
)

# Valid fields within a category
VALID_CATEGORY_FIELDS = frozenset(
    ["description", "subcategories", "notes", "examples", "human_verified", "ai_confidence"]
)


def _validate_category_name(category: str) -> None:
    """
    Validate grammar category name.

    Args:
        category: Category name to validate

    Raises:
        ToolError: If category name is invalid
    """
    if category not in VALID_CATEGORIES:
        raise ToolError(
            "invalid_category",
            f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
            {"category": category, "valid_categories": list(VALID_CATEGORIES)},
        )


def _has_content(category_data: dict) -> bool:
    """Check if a category has any content (notes, examples, or description)."""
    if category_data.get("description"):
        return True
    if category_data.get("notes"):
        return True
    if category_data.get("examples"):
        return True
    return False


async def _get_grammar_doc(db, language_code: str) -> dict | None:
    """
    Get grammar system document for a language.

    Args:
        db: MongoDBConnector instance
        language_code: Language code

    Returns:
        Grammar system document or None
    """
    grammar_systems = db.get_collection("grammar_systems")
    return await grammar_systems.find_one({"language_code": language_code.lower()})


async def list_grammar_categories(db, language_code: str) -> dict[str, Any]:
    """
    List all grammar categories with content status.

    Args:
        db: MongoDBConnector instance
        language_code: Language to get categories for

    Returns:
        {
            "categories": [{name, has_content, description?}],
            "count": int
        }
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Get grammar document
    doc = await _get_grammar_doc(db, language_code)

    if doc is None:
        return success_response({"categories": [], "count": 0})

    categories_data = doc.get("categories", {})
    categories = []

    for name in VALID_CATEGORIES:
        cat_data = categories_data.get(name, {})
        categories.append(
            {
                "name": name,
                "has_content": _has_content(cat_data),
                "description": cat_data.get("description", ""),
            }
        )

    return success_response({"categories": categories, "count": len(categories)})


async def get_grammar_category(
    db,
    language_code: str,
    category: str,
) -> dict[str, Any]:
    """
    Get specific grammar category content.

    Args:
        db: MongoDBConnector instance
        language_code: Language to get category for
        category: Category name (phonology, morphology, syntax, semantics, discourse)

    Returns:
        Category content with name, description, subcategories, notes, examples
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate category name
    try:
        _validate_category_name(category)
    except ToolError as e:
        return error_response(e)

    # Get grammar document
    doc = await _get_grammar_doc(db, language_code)

    if doc is None:
        return error_response(
            ToolError(
                "not_found",
                f"No grammar system found for language '{language_code}'",
                {"language_code": language_code},
            )
        )

    categories_data = doc.get("categories", {})
    cat_data = categories_data.get(category, {})

    return {
        "name": category,
        "description": cat_data.get("description", ""),
        "subcategories": cat_data.get("subcategories", []),
        "notes": cat_data.get("notes", []),
        "examples": cat_data.get("examples", []),
        "human_verified": cat_data.get("human_verified", False),
    }


async def update_grammar_category(
    db,
    language_code: str,
    category: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """
    Update grammar category content.

    Args:
        db: MongoDBConnector instance
        language_code: Target language
        category: Category name to update
        content: Fields to update (description, subcategories, notes, examples)

    Returns:
        {"success": bool, "updated_at": str}
    """
    # Validate language exists
    try:
        await validate_language(db, language_code)
    except ToolError as e:
        return error_response(e)

    # Validate category name
    try:
        _validate_category_name(category)
    except ToolError as e:
        return error_response(e)

    # Validate and sanitize content via Pydantic model
    try:
        validated = GrammarUpdateInput.model_validate(content)
        content = validated.model_dump(exclude_unset=True)
    except ValidationError as e:
        return error_response(
            ToolError(
                "validation_error",
                str(e),
                {"content": content},
            )
        )

    grammar_systems = db.get_collection("grammar_systems")
    now = datetime.now(timezone.utc)

    # Get existing document
    doc = await _get_grammar_doc(db, language_code)

    if doc is None:
        # Create new grammar system with this category
        empty_category = {
            "description": "",
            "subcategories": [],
            "notes": [],
            "examples": [],
        }

        # Build categories with all 5, populating the one being updated
        categories = {}
        for cat_name in VALID_CATEGORIES:
            if cat_name == category:
                # Filter content to valid fields only
                filtered = {
                    k: v for k, v in content.items() if k in VALID_CATEGORY_FIELDS
                }
                categories[cat_name] = {**empty_category, **filtered, "updated_at": now}
            else:
                categories[cat_name] = {**empty_category}

        new_doc = {
            "language_code": language_code.lower(),
            "categories": categories,
            "created_at": now,
        }
        await grammar_systems.insert_one(new_doc)

        return success_response({"success": True, "updated_at": now.isoformat()})

    # Build $set operations for partial update
    update_ops = {}
    for field, value in content.items():
        if field in VALID_CATEGORY_FIELDS:
            update_ops[f"categories.{category}.{field}"] = value

    # Always update timestamp
    update_ops[f"categories.{category}.updated_at"] = now

    await grammar_systems.update_one({"_id": doc["_id"]}, {"$set": update_ops})

    return success_response({"success": True, "updated_at": now.isoformat()})
