import logging

import pytest

from shared.logging_setup import redact, _RedactingFormatter


class TestRedact:
    def test_strips_userinfo_from_uri(self):
        assert redact("mongodb://nlm_app:s3cret@localhost:27019/db") == "mongodb://localhost:27019/db"

    def test_strips_userinfo_from_srv_uri(self):
        text = "connecting to mongodb+srv://user:p%40ss@cluster0.mongodb.net/db failed"
        assert redact(text) == "connecting to mongodb+srv://cluster0.mongodb.net/db failed"

    def test_leaves_uri_without_userinfo_untouched(self):
        text = "mongodb://localhost:27019/db"
        assert redact(text) == text

    def test_leaves_plain_text_untouched(self):
        text = "connection refused after 5.0s"
        assert redact(text) == text

    def test_strips_multiple_uris_in_one_string(self):
        text = "primary mongodb://a:b@host1/db, fallback mongodb://c:d@host2/db"
        assert redact(text) == "primary mongodb://host1/db, fallback mongodb://host2/db"

    def test_bare_password_without_uri_wrapper_is_not_redacted(self):
        # Documented limit: redact() only strips //<userinfo>@, not a bare
        # password appearing alone in a message.
        text = "password s3cret rejected"
        assert redact(text) == text


class TestRedactingFormatter:
    def test_traceback_text_is_redacted(self):
        # The traceback is rendered inside Formatter.format() (formatException),
        # after any Filter has run — so only overriding format() catches a
        # credential embedded in an exception's own str().
        formatter = _RedactingFormatter("%(levelname)s: %(message)s")
        try:
            raise ValueError("connect failed: mongodb://nlm_app:s3cret@localhost:27019/db")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="db_connector.connection", level=logging.ERROR,
                pathname=__file__, lineno=1, msg="Connection error",
                args=(), exc_info=sys.exc_info(),
            )
        out = formatter.format(record)
        assert "Traceback" in out          # traceback really was rendered
        assert "s3cret" not in out
        assert "mongodb://localhost:27019/db" in out
