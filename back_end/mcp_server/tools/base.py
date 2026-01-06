"""
Base utilities for MCP server tools.

Provides:
- ToolError exception for structured error responses
- Response helpers (success_response, error_response)
- Common validators (validate_language, validate_translation_type, validate_book_code)
- File output utilities (validate_filename, save_result_to_file)
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.schema_enforcer.schema_definition import (
    VALID_TRANSLATION_TYPES,
    BOOK_CODE_PATTERN,
)


class ToolError(Exception):
    """
    Structured error for MCP tool failures.

    Attributes:
        code: Error type identifier (e.g., "not_found", "invalid_input")
        message: Human-readable error description
        details: Additional context as key-value pairs
    """

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(error: ToolError) -> dict[str, Any]:
    """
    Convert ToolError to structured response dict.

    Returns:
        {"error": {"code": str, "message": str, "details": dict}}
    """
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        }
    }


def success_response(
    data: dict[str, Any], metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Wrap successful response data.

    Args:
        data: The response payload
        metadata: Optional contextual information (e.g., notes about edge cases)

    Returns:
        The data dict, with optional "metadata" key added
    """
    response = dict(data)
    if metadata is not None:
        response["metadata"] = metadata
    return response


async def validate_language(db, language_code: str) -> dict[str, Any]:
    """
    Validate that a language exists and return its document.

    Args:
        db: MongoDBConnector instance
        language_code: The language code to validate (case-insensitive)

    Returns:
        The language document if found

    Raises:
        ToolError: If language doesn't exist (code="not_found")
    """
    languages = db.get_collection("languages")

    # Case-insensitive lookup
    doc = await languages.find_one(
        {"language_code": {"$regex": f"^{re.escape(language_code)}$", "$options": "i"}}
    )

    if doc is None:
        raise ToolError(
            "not_found",
            f"Language '{language_code}' not found",
            {"language_code": language_code},
        )

    return doc


def validate_translation_type(translation_type: str | None) -> None:
    """
    Validate translation type parameter.

    Args:
        translation_type: "human", "ai", or None (meaning both)

    Raises:
        ToolError: If translation_type is invalid (code="invalid_input")
    """
    if translation_type is None:
        return  # None means "both types", which is valid

    if translation_type not in VALID_TRANSLATION_TYPES:
        raise ToolError(
            "invalid_input",
            f"Invalid translation_type '{translation_type}'. Must be one of: {', '.join(sorted(VALID_TRANSLATION_TYPES))}",
            {"translation_type": translation_type, "valid_types": list(VALID_TRANSLATION_TYPES)},
        )


def validate_book_code(book_code: str) -> str:
    """
    Validate and normalize book code.

    Args:
        book_code: Book code to validate (e.g., "genesis", "1_chronicles")

    Returns:
        Normalized (lowercase) book code

    Raises:
        ToolError: If book_code format is invalid (code="invalid_input")
    """
    normalized = book_code.lower()

    if not re.match(BOOK_CODE_PATTERN, normalized):
        raise ToolError(
            "invalid_input",
            f"Invalid book_code '{book_code}'. Must be lowercase alphanumeric with underscores.",
            {"book_code": book_code, "pattern": BOOK_CODE_PATTERN},
        )

    return normalized


# =============================================================================
# File Output Utilities
# =============================================================================

# Directory for temp file output (relative to this file: tools/../temp_files)
TEMP_FILES_DIR = Path(__file__).parent.parent / "temp_files"

# Strict filename pattern: alphanumeric, underscore, hyphen only
VALID_FILENAME_PATTERN = r"^[a-zA-Z0-9_-]+$"


def validate_filename(filename: str) -> str:
    """
    Validate and sanitize filename for temp file output.

    Security rules:
    - Alphanumeric, underscore, hyphen only
    - No path separators or traversal (../)
    - Auto-appends .json if missing

    Args:
        filename: Requested filename (e.g., "bughotu_verses_1")

    Returns:
        Sanitized filename with .json extension

    Raises:
        ToolError: If filename contains invalid characters (code="invalid_input")
    """
    # Strip any path components (security: prevents directory traversal)
    basename = Path(filename).name

    # Remove .json extension for validation, add back later
    if basename.endswith(".json"):
        basename = basename[:-5]

    # Reject empty or whitespace-only
    if not basename or not basename.strip():
        raise ToolError(
            "invalid_input",
            "Filename cannot be empty",
            {"filename": filename},
        )

    # Strict pattern: alphanumeric, underscore, hyphen
    if not re.match(VALID_FILENAME_PATTERN, basename):
        raise ToolError(
            "invalid_input",
            f"Invalid filename '{filename}'. Use only letters, numbers, underscore, hyphen.",
            {"filename": filename, "pattern": VALID_FILENAME_PATTERN},
        )

    return f"{basename}.json"


def save_result_to_file(
    data: dict[str, Any],
    filename: str | None = None,
    prefix: str = "result",
) -> dict[str, Any]:
    """
    Save result data to temp file instead of returning inline.

    Args:
        data: The result dict to save (will be JSON-serialized)
        filename: Optional filename (validated). If None, generates timestamped name.
        prefix: Prefix for auto-generated filename (e.g., "bughotu_verses")

    Returns:
        {"saved_to": "/absolute/path/file.json", "record_count": N, "filename": "file.json"}

    Raises:
        ToolError: On validation failure or write error
    """
    # Ensure directory exists
    TEMP_FILES_DIR.mkdir(parents=True, exist_ok=True)

    # Generate or validate filename
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        validated_filename = f"{prefix}_{timestamp}.json"
    else:
        validated_filename = validate_filename(filename)

    filepath = TEMP_FILES_DIR / validated_filename

    # Count records (look for common list keys in response)
    record_count = 0
    for key in ["verses", "entries", "books", "categories", "languages"]:
        if key in data and isinstance(data[key], list):
            record_count = len(data[key])
            break

    # Write file
    try:
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except OSError as e:
        raise ToolError(
            "write_error",
            f"Failed to write file: {e}",
            {"filepath": str(filepath), "error": str(e)},
        )

    return {
        "saved_to": str(filepath.resolve()),
        "record_count": record_count,
        "filename": validated_filename,
    }
