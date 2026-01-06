"""
Validators - Pure validation functions using factory pattern.

All validators return List[str] of issues (empty list = valid).
This module contains no side effects - purely functional validation.
"""

import re
from typing import Any, Callable

from utils.schema_enforcer.schema_definition import (
    BOOK_CODE_PATTERN,
    VALID_TRANSLATION_TYPES,
    BOOK_ORDER_RANGE,
)


# Type alias for validator functions
ValidatorFunc = Callable[[Any], list[str]]


# =============================================================================
# VALIDATOR FACTORIES
# =============================================================================


def enum_validator(allowed: set, field_name: str) -> ValidatorFunc:
    """
    Factory for enum/set membership validation.

    Args:
        allowed: Set of valid values
        field_name: Name of field (for error messages)

    Returns:
        Validator function: (value) -> List[str]
    """

    def validate(value: Any) -> list[str]:
        if value not in allowed:
            return [f"{field_name} '{value}' not in {allowed}"]
        return []

    return validate


def range_validator(min_val: int, max_val: int, field_name: str) -> ValidatorFunc:
    """
    Factory for numeric range validation.

    Args:
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        field_name: Name of field (for error messages)

    Returns:
        Validator function: (value) -> List[str]
    """

    def validate(value: Any) -> list[str]:
        if not isinstance(value, int):
            return [f"{field_name} must be int, got {type(value).__name__}"]
        if not min_val <= value <= max_val:
            return [f"{field_name} {value} not in [{min_val}, {max_val}]"]
        return []

    return validate


def pattern_validator(pattern: str, field_name: str) -> ValidatorFunc:
    """
    Factory for regex pattern validation.

    Args:
        pattern: Regex pattern string
        field_name: Name of field (for error messages)

    Returns:
        Validator function: (value) -> List[str]
    """
    compiled = re.compile(pattern)

    def validate(value: Any) -> list[str]:
        if not isinstance(value, str):
            return [f"{field_name} must be str, got {type(value).__name__}"]
        if not compiled.match(value):
            return [f"{field_name} '{value}' doesn't match pattern {pattern}"]
        return []

    return validate


# =============================================================================
# INSTANTIATED VALIDATORS (from factories)
# =============================================================================

validate_translation_type: ValidatorFunc = enum_validator(
    VALID_TRANSLATION_TYPES, "translation_type"
)

validate_book_order: ValidatorFunc = range_validator(
    BOOK_ORDER_RANGE[0], BOOK_ORDER_RANGE[1], "book_order"
)

validate_book_code: ValidatorFunc = pattern_validator(BOOK_CODE_PATTERN, "book_code")


# =============================================================================
# COMPOSITE VALIDATORS
# =============================================================================


def validate_field_type(field_name: str, value: Any, expected_type: type) -> list[str]:
    """
    Validate that a field value matches the expected type.

    Args:
        field_name: Name of the field
        value: Value to check
        expected_type: Expected Python type

    Returns:
        List of issues (empty if valid)
    """
    # Handle "datetime" string type specially
    if expected_type == "datetime":
        # Accept datetime objects or ISO format strings
        from datetime import datetime

        if isinstance(value, datetime):
            return []
        if isinstance(value, str):
            # Could add ISO format validation here
            return []
        return [f"{field_name} must be datetime or ISO string, got {type(value).__name__}"]

    if not isinstance(value, expected_type):
        return [f"{field_name} must be {expected_type.__name__}, got {type(value).__name__}"]
    return []


def validate_required_fields(doc: dict, schema: dict) -> list[str]:
    """
    Validate that a document has all required fields.

    Args:
        doc: MongoDB document to validate
        schema: Schema dict containing 'required_fields'

    Returns:
        List of issues (empty if all required fields present)
    """
    issues = []
    required_fields = schema.get("required_fields", {})

    for field_name, field_type in required_fields.items():
        if field_name not in doc:
            issues.append(f"Missing required field: {field_name}")
        else:
            # Type check
            type_issues = validate_field_type(field_name, doc[field_name], field_type)
            issues.extend(type_issues)

    return issues


def validate_document(doc: dict, schema: dict, collection_name: str) -> list[str]:
    """
    Full validation of a document against its schema.

    Args:
        doc: MongoDB document to validate
        schema: Schema dict from EXPECTED_COLLECTIONS
        collection_name: Name of collection (for context in errors)

    Returns:
        List of issues (empty if valid)
    """
    issues = []

    # Required fields
    issues.extend(validate_required_fields(doc, schema))

    # Collection-specific validations
    if collection_name == "bible_texts":
        if "book_code" in doc:
            issues.extend(validate_book_code(doc["book_code"]))
        if "translation_type" in doc:
            issues.extend(validate_translation_type(doc["translation_type"]))

    elif collection_name == "base_structure_bible":
        if "book_order" in doc:
            issues.extend(validate_book_order(doc["book_order"]))

    elif collection_name in ("dictionaries", "grammar_systems"):
        if "translation_type" in doc:
            issues.extend(validate_translation_type(doc["translation_type"]))

    return issues
