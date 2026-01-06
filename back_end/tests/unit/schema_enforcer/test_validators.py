"""
Tests for validators.py - Pure validation functions using factory pattern.

TDD Step 3: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/schema_enforcer/test_validators.py -v
"""

import pytest


class TestRequiredFieldsValidation:
    """Tests for validate_required_fields function"""

    def test_validate_required_fields_all_present(self):
        """Returns empty list when all required fields present"""
        from utils.schema_enforcer.validators import validate_required_fields
        from utils.schema_enforcer.schema_definition import EXPECTED_COLLECTIONS

        doc = {
            "language_code": "english",
            "book_code": "genesis",
            "chapter": 1,
            "verse": 1,
            "translation_type": "human",
            "created_at": "2024-01-01T00:00:00Z",
        }
        schema = EXPECTED_COLLECTIONS["bible_texts"]
        issues = validate_required_fields(doc, schema)
        assert issues == []

    def test_validate_required_fields_missing_one(self):
        """Returns issue when required field missing"""
        from utils.schema_enforcer.validators import validate_required_fields
        from utils.schema_enforcer.schema_definition import EXPECTED_COLLECTIONS

        doc = {"language_code": "test"}  # missing book_code, chapter, etc.
        schema = EXPECTED_COLLECTIONS["bible_texts"]
        issues = validate_required_fields(doc, schema)

        assert len(issues) > 0
        assert any("book_code" in str(issue) for issue in issues)


class TestFieldTypeValidation:
    """Tests for validate_field_type function"""

    def test_validate_field_type_correct(self):
        """Returns empty when field type matches"""
        from utils.schema_enforcer.validators import validate_field_type

        issues = validate_field_type("chapter", 1, int)
        assert issues == []

    def test_validate_field_type_wrong(self):
        """Returns issue when type doesn't match"""
        from utils.schema_enforcer.validators import validate_field_type

        issues = validate_field_type("chapter", "one", int)
        assert len(issues) == 1
        assert "chapter" in issues[0]


class TestBookCodeValidation:
    """Tests for validate_book_code validator"""

    def test_validate_book_code_format_valid(self):
        """Accepts lowercase with underscores"""
        from utils.schema_enforcer.validators import validate_book_code

        assert validate_book_code("genesis") == []
        assert validate_book_code("1_chronicles") == []
        assert validate_book_code("song_of_solomon") == []

    def test_validate_book_code_format_invalid(self):
        """Rejects uppercase, spaces, abbreviations"""
        from utils.schema_enforcer.validators import validate_book_code

        assert len(validate_book_code("Genesis")) > 0  # Uppercase
        assert len(validate_book_code("GEN")) > 0  # All caps abbreviation
        assert len(validate_book_code("1 chronicles")) > 0  # Space


class TestTranslationTypeValidation:
    """Tests for validate_translation_type validator"""

    def test_validate_translation_type_valid(self):
        """Accepts 'human' and 'ai'"""
        from utils.schema_enforcer.validators import validate_translation_type

        assert validate_translation_type("human") == []
        assert validate_translation_type("ai") == []

    def test_validate_translation_type_invalid(self):
        """Rejects other values"""
        from utils.schema_enforcer.validators import validate_translation_type

        assert len(validate_translation_type("machine")) > 0
        assert len(validate_translation_type("")) > 0
        assert len(validate_translation_type("Human")) > 0  # Case sensitive


class TestBookOrderValidation:
    """Tests for validate_book_order validator"""

    def test_validate_book_order_valid(self):
        """Accepts 1-66 range"""
        from utils.schema_enforcer.validators import validate_book_order

        assert validate_book_order(1) == []
        assert validate_book_order(66) == []
        assert validate_book_order(33) == []

    def test_validate_book_order_invalid(self):
        """Rejects out of range values"""
        from utils.schema_enforcer.validators import validate_book_order

        assert len(validate_book_order(0)) > 0
        assert len(validate_book_order(67)) > 0
        assert len(validate_book_order(-1)) > 0


class TestValidatorFactories:
    """Tests for validator factory functions"""

    def test_enum_validator_factory(self):
        """enum_validator creates working validator"""
        from utils.schema_enforcer.validators import enum_validator

        validate_status = enum_validator({"active", "inactive"}, "status")

        assert validate_status("active") == []
        assert validate_status("inactive") == []
        assert len(validate_status("pending")) > 0

    def test_range_validator_factory(self):
        """range_validator creates working validator"""
        from utils.schema_enforcer.validators import range_validator

        validate_chapter = range_validator(1, 150, "chapter")

        assert validate_chapter(1) == []
        assert validate_chapter(150) == []
        assert len(validate_chapter(0)) > 0
        assert len(validate_chapter(151)) > 0

    def test_pattern_validator_factory(self):
        """pattern_validator creates working validator"""
        from utils.schema_enforcer.validators import pattern_validator

        validate_code = pattern_validator(r"^[a-z]+$", "code")

        assert validate_code("abc") == []
        assert len(validate_code("ABC")) > 0
        assert len(validate_code("123")) > 0
