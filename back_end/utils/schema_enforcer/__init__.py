# Schema Enforcer
# Ensures MongoDB schema consistency with single source of truth

from utils.schema_enforcer.schema_definition import (
    EXPECTED_COLLECTIONS,
    DEPRECATED_COLLECTIONS,
    SCHEMA_VERSION,
    BOOK_CODE_PATTERN,
    VALID_TRANSLATION_TYPES,
    BOOK_ORDER_RANGE,
)
from utils.schema_enforcer.report import EnforcementReport
from utils.schema_enforcer.enforcer import SchemaEnforcer
from utils.schema_enforcer.validators import (
    validate_book_code,
    validate_translation_type,
    validate_book_order,
    validate_document,
    validate_required_fields,
)

__all__ = [
    # Schema definition
    "EXPECTED_COLLECTIONS",
    "DEPRECATED_COLLECTIONS",
    "SCHEMA_VERSION",
    "BOOK_CODE_PATTERN",
    "VALID_TRANSLATION_TYPES",
    "BOOK_ORDER_RANGE",
    # Classes
    "EnforcementReport",
    "SchemaEnforcer",
    # Validators
    "validate_book_code",
    "validate_translation_type",
    "validate_book_order",
    "validate_document",
    "validate_required_fields",
]
