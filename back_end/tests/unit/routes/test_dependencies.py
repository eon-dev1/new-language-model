# tests/unit/routes/test_dependencies.py
"""
Tests for routes/dependencies.py — api_error must not leak exception text.
"""

from routes.dependencies import api_error


def test_api_error_does_not_leak_exception_text():
    exc = api_error("do the thing", RuntimeError("SENTINEL_SECRET"))
    assert "SENTINEL_SECRET" not in exc.detail
    assert exc.detail == "do the thing failed"
