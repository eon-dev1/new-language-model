"""
Tests for mcp_server/tools/base.py - Foundation utilities.

TDD: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/mcp_server/test_base.py -v
"""

import pytest


class TestToolError:
    """Tests for ToolError exception class"""

    def test_tool_error_has_code_and_message(self):
        """ToolError stores error code and message"""
        from mcp_server.tools.base import ToolError

        err = ToolError("not_found", "Language 'xyz' not found")
        assert err.code == "not_found"
        assert err.message == "Language 'xyz' not found"

    def test_tool_error_has_optional_details(self):
        """ToolError can include additional details dict"""
        from mcp_server.tools.base import ToolError

        err = ToolError("not_found", "Not found", details={"id": "xyz"})
        assert err.details == {"id": "xyz"}

    def test_tool_error_details_default_empty(self):
        """ToolError details defaults to empty dict"""
        from mcp_server.tools.base import ToolError

        err = ToolError("error", "Something went wrong")
        assert err.details == {}

    def test_tool_error_is_exception(self):
        """ToolError can be raised and caught"""
        from mcp_server.tools.base import ToolError

        with pytest.raises(ToolError) as exc_info:
            raise ToolError("test_error", "Test message")

        assert exc_info.value.code == "test_error"


class TestErrorResponse:
    """Tests for error_response helper"""

    def test_error_response_from_tool_error(self):
        """error_response converts ToolError to dict"""
        from mcp_server.tools.base import ToolError, error_response

        err = ToolError("not_found", "Language 'xyz' not found", {"language_code": "xyz"})
        response = error_response(err)

        assert response == {
            "error": {
                "code": "not_found",
                "message": "Language 'xyz' not found",
                "details": {"language_code": "xyz"},
            }
        }

    def test_error_response_shape(self):
        """error_response always has 'error' key with code, message, details"""
        from mcp_server.tools.base import ToolError, error_response

        err = ToolError("validation_error", "Invalid input")
        response = error_response(err)

        assert "error" in response
        assert "code" in response["error"]
        assert "message" in response["error"]
        assert "details" in response["error"]


class TestSuccessResponse:
    """Tests for success_response helper"""

    def test_success_response_passes_data_through(self):
        """success_response wraps data dict"""
        from mcp_server.tools.base import success_response

        data = {"languages": [{"code": "heb"}], "count": 1}
        response = success_response(data)

        assert response["languages"] == [{"code": "heb"}]
        assert response["count"] == 1

    def test_success_response_adds_metadata_when_provided(self):
        """success_response includes optional metadata"""
        from mcp_server.tools.base import success_response

        data = {"items": []}
        response = success_response(data, metadata={"note": "English has no AI version"})

        assert response["items"] == []
        assert response["metadata"] == {"note": "English has no AI version"}

    def test_success_response_no_metadata_by_default(self):
        """success_response omits metadata key when not provided"""
        from mcp_server.tools.base import success_response

        data = {"count": 5}
        response = success_response(data)

        assert "metadata" not in response


class TestValidateLanguage:
    """Tests for validate_language async helper"""

    @pytest.mark.asyncio
    async def test_validate_language_returns_doc_when_exists(self, mock_mcp_db):
        """validate_language returns language document if found"""
        from mcp_server.tools.base import validate_language

        # mock_mcp_db fixture has "english" and "heb" languages
        result = await validate_language(mock_mcp_db, "english")

        assert result["language_code"] == "english"
        assert result["language_name"] == "English"

    @pytest.mark.asyncio
    async def test_validate_language_raises_not_found(self, mock_mcp_db):
        """validate_language raises ToolError if language doesn't exist"""
        from mcp_server.tools.base import ToolError, validate_language

        with pytest.raises(ToolError) as exc_info:
            await validate_language(mock_mcp_db, "nonexistent")

        assert exc_info.value.code == "not_found"
        assert "nonexistent" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validate_language_case_insensitive(self, mock_mcp_db):
        """validate_language handles case variations"""
        from mcp_server.tools.base import validate_language

        # Should find "english" even with different case
        result = await validate_language(mock_mcp_db, "ENGLISH")
        assert result["language_code"] == "english"


class TestValidateTranslationType:
    """Tests for validate_translation_type helper"""

    def test_validate_translation_type_accepts_human(self):
        """'human' is valid translation type"""
        from mcp_server.tools.base import validate_translation_type

        # Should not raise
        validate_translation_type("human")

    def test_validate_translation_type_accepts_ai(self):
        """'ai' is valid translation type"""
        from mcp_server.tools.base import validate_translation_type

        validate_translation_type("ai")

    def test_validate_translation_type_accepts_none(self):
        """None is valid (means 'both types')"""
        from mcp_server.tools.base import validate_translation_type

        validate_translation_type(None)

    def test_validate_translation_type_rejects_invalid(self):
        """Invalid translation type raises ToolError"""
        from mcp_server.tools.base import ToolError, validate_translation_type

        with pytest.raises(ToolError) as exc_info:
            validate_translation_type("invalid")

        assert exc_info.value.code == "invalid_input"


class TestValidateBookCode:
    """Tests for validate_book_code helper"""

    def test_validate_book_code_accepts_lowercase(self):
        """Lowercase book codes are valid"""
        from mcp_server.tools.base import validate_book_code

        result = validate_book_code("genesis")
        assert result == "genesis"

    def test_validate_book_code_normalizes_uppercase(self):
        """Uppercase codes are normalized to lowercase"""
        from mcp_server.tools.base import validate_book_code

        result = validate_book_code("GENESIS")
        assert result == "genesis"

    def test_validate_book_code_handles_underscores(self):
        """Book codes with underscores are valid"""
        from mcp_server.tools.base import validate_book_code

        result = validate_book_code("1_chronicles")
        assert result == "1_chronicles"

    def test_validate_book_code_rejects_invalid_chars(self):
        """Book codes with invalid characters raise ToolError"""
        from mcp_server.tools.base import ToolError, validate_book_code

        with pytest.raises(ToolError) as exc_info:
            validate_book_code("genesis!")

        assert exc_info.value.code == "invalid_input"


# =============================================================================
# File Output Utilities Tests
# =============================================================================


class TestValidateFilename:
    """Tests for validate_filename helper (file save security)"""

    def test_validate_filename_accepts_alphanumeric(self):
        """Alphanumeric filenames are valid"""
        from mcp_server.tools.base import validate_filename

        result = validate_filename("myfile123")
        assert result == "myfile123.json"

    def test_validate_filename_accepts_underscore(self):
        """Underscores are allowed in filenames"""
        from mcp_server.tools.base import validate_filename

        result = validate_filename("bughotu_verses_batch1")
        assert result == "bughotu_verses_batch1.json"

    def test_validate_filename_accepts_hyphen(self):
        """Hyphens are allowed in filenames"""
        from mcp_server.tools.base import validate_filename

        result = validate_filename("my-file-name")
        assert result == "my-file-name.json"

    def test_validate_filename_preserves_json_extension(self):
        """Existing .json extension is preserved"""
        from mcp_server.tools.base import validate_filename

        result = validate_filename("myfile.json")
        assert result == "myfile.json"

    def test_validate_filename_strips_path_traversal(self):
        """Path traversal attempts have path stripped, only basename validated"""
        from mcp_server.tools.base import ToolError, validate_filename

        # "../etc/passwd" -> basename is "passwd" which is valid
        result = validate_filename("../etc/passwd")
        assert result == "passwd.json"

    def test_validate_filename_rejects_empty(self):
        """Empty filename raises ToolError"""
        from mcp_server.tools.base import ToolError, validate_filename

        with pytest.raises(ToolError) as exc_info:
            validate_filename("")

        assert exc_info.value.code == "invalid_input"
        assert "empty" in exc_info.value.message.lower()

    def test_validate_filename_rejects_whitespace_only(self):
        """Whitespace-only filename raises ToolError"""
        from mcp_server.tools.base import ToolError, validate_filename

        with pytest.raises(ToolError) as exc_info:
            validate_filename("   ")

        assert exc_info.value.code == "invalid_input"

    def test_validate_filename_rejects_spaces(self):
        """Filenames with spaces are rejected"""
        from mcp_server.tools.base import ToolError, validate_filename

        with pytest.raises(ToolError) as exc_info:
            validate_filename("my file")

        assert exc_info.value.code == "invalid_input"

    def test_validate_filename_rejects_special_chars(self):
        """Special characters are rejected"""
        from mcp_server.tools.base import ToolError, validate_filename

        for invalid in ["foo!bar", "foo@bar", "foo#bar", "foo$bar", "foo.bar.baz"]:
            with pytest.raises(ToolError) as exc_info:
                validate_filename(invalid)

            assert exc_info.value.code == "invalid_input"


class TestSaveResultToFile:
    """Tests for save_result_to_file helper"""

    def test_save_result_creates_file(self, tmp_path, monkeypatch):
        """File is created in TEMP_FILES_DIR"""
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file

        # Redirect TEMP_FILES_DIR to tmp_path
        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        data = {"verses": [{"verse": 1, "text": "test"}], "total": 1}
        result = save_result_to_file(data, filename="test_output")

        # File should exist
        assert (tmp_path / "test_output.json").exists()

    def test_save_result_returns_correct_shape(self, tmp_path, monkeypatch):
        """Return dict has saved_to, record_count, filename"""
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        data = {"verses": [{"v": 1}, {"v": 2}], "total": 2}
        result = save_result_to_file(data, filename="output")

        assert "saved_to" in result
        assert "record_count" in result
        assert "filename" in result
        assert result["record_count"] == 2
        assert result["filename"] == "output.json"

    def test_save_result_counts_verses(self, tmp_path, monkeypatch):
        """Record count extracted from 'verses' key"""
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        data = {"verses": [1, 2, 3, 4, 5], "total": 100}
        result = save_result_to_file(data, filename="verses_test")

        assert result["record_count"] == 5

    def test_save_result_counts_entries(self, tmp_path, monkeypatch):
        """Record count extracted from 'entries' key"""
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        data = {"entries": [{"word": "a"}, {"word": "b"}]}
        result = save_result_to_file(data, filename="entries_test")

        assert result["record_count"] == 2

    def test_save_result_auto_generates_filename(self, tmp_path, monkeypatch):
        """When filename is None, generates timestamped name"""
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        data = {"items": [1, 2, 3]}
        result = save_result_to_file(data, filename=None, prefix="test_prefix")

        # Filename should start with prefix and end with .json
        assert result["filename"].startswith("test_prefix_")
        assert result["filename"].endswith(".json")

    def test_save_result_creates_directory_if_missing(self, tmp_path, monkeypatch):
        """Creates TEMP_FILES_DIR if it doesn't exist"""
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file

        # Point to a non-existent subdirectory
        new_dir = tmp_path / "subdir" / "nested"
        monkeypatch.setattr(base, "TEMP_FILES_DIR", new_dir)

        data = {"verses": []}
        result = save_result_to_file(data, filename="test")

        assert new_dir.exists()
        assert (new_dir / "test.json").exists()

    def test_save_result_absolute_path_in_saved_to(self, tmp_path, monkeypatch):
        """saved_to contains absolute path"""
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file
        from pathlib import Path

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        data = {"verses": []}
        result = save_result_to_file(data, filename="abs_test")

        saved_path = Path(result["saved_to"])
        assert saved_path.is_absolute()

    def test_save_result_file_contains_json(self, tmp_path, monkeypatch):
        """Saved file contains valid JSON matching input data"""
        import json
        from mcp_server.tools import base
        from mcp_server.tools.base import save_result_to_file

        monkeypatch.setattr(base, "TEMP_FILES_DIR", tmp_path)

        data = {"verses": [{"verse": 1, "text": "Hello"}], "total": 1}
        result = save_result_to_file(data, filename="json_test")

        # Read back and verify
        saved_file = tmp_path / "json_test.json"
        content = json.loads(saved_file.read_text())
        assert content == data
