"""
Validators - Pure validation functions using factory pattern.

All validators return List[str] of issues (empty list = valid).
This module contains no side effects - purely functional validation.
"""

import re
from typing import Any, Callable

from utils.schema_enforcer.schema_definition import (
    BOOK_CODE_PATTERN,
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


def validate_embedded_schema(doc: dict, schema: dict, collection_name: str) -> list[str]:
    """
    Recurse into a collection schema's `embedded_schema` block, validating
    each declared embedded field's contents against its own sub-schema.

    A field is treated as a list of embedded documents or a single embedded
    document based on `required_fields[field_name]` in the parent schema
    (list vs dict) — NOT by inspecting the value at runtime. Two sibling
    fields in the same schema (e.g. bible_books.chapters is a list,
    bible_books.metadata is a dict) must be handled differently, and a
    value-based guess would silently misvalidate one of them.

    Args:
        doc: MongoDB document to validate
        schema: Schema dict from EXPECTED_COLLECTIONS
        collection_name: Name of collection (for prefixing issue messages)

    Returns:
        List of issues (empty if valid or nothing to recurse into)
    """
    issues = []
    embedded_schema = schema.get("embedded_schema", {})
    required_fields = schema.get("required_fields", {})

    for field_name, sub_schema in embedded_schema.items():
        value = doc.get(field_name)
        if value is None:
            continue

        field_type = required_fields.get(field_name)

        if field_type is list:
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                for sub_issue in validate_required_fields(item, sub_schema):
                    issues.append(f"{collection_name}.{field_name}[]: {sub_issue}")
        elif field_type is dict:
            if not isinstance(value, dict):
                continue
            for sub_issue in validate_required_fields(value, sub_schema):
                issues.append(f"{collection_name}.{field_name}: {sub_issue}")
        # else: field type not declared as list or dict — nothing safe to recurse into

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

    # Embedded-list/dict shape drift
    issues.extend(validate_embedded_schema(doc, schema, collection_name))

    # Collection-specific validations
    if collection_name == "bible_texts":
        if "book_code" in doc:
            issues.extend(validate_book_code(doc["book_code"]))

    elif collection_name == "base_structure_bible":
        if "book_order" in doc:
            issues.extend(validate_book_order(doc["book_order"]))

    return issues
