import logging


def test_root_handlers_redact_credentials():
    # Proves redaction works via the top-level tests/conftest.py call to
    # install_logging() alone — this suite never imports main.py, so if
    # this passes, redaction isn't accidentally main.py-only.
    root_logger = logging.getLogger()
    assert root_logger.handlers, "install_logging() should have attached at least one handler"

    record = logging.LogRecord(
        name="db_connector.connection",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Failed to connect to MongoDB: mongodb://nlm_app:s3cret@localhost:27019/db",
        args=(),
        exc_info=None,
    )
    outputs = []
    for handler in root_logger.handlers:
        for log_filter in handler.filters:
            log_filter.filter(record)
        outputs.append(handler.format(record))
    assert any("s3cret" not in out and "mongodb://localhost:27019/db" in out for out in outputs)
