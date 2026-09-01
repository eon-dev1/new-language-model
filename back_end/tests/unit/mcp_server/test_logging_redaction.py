import logging


def test_root_handlers_redact_credentials():
    # Confirms this suite genuinely runs through mcp_server, not main.py.
    from mcp_server.server import mcp

    assert mcp is not None

    root_logger = logging.getLogger()
    assert root_logger.handlers, "install_logging() should have attached at least one handler"

    record = logging.LogRecord(
        name="mcp_server.server",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="connect failed: mongodb://nlm_app:s3cret@localhost:27019/db",
        args=(),
        exc_info=None,
    )
    outputs = []
    for handler in root_logger.handlers:
        for log_filter in handler.filters:
            log_filter.filter(record)
        outputs.append(handler.format(record))
    assert any("s3cret" not in out and "mongodb://localhost:27019/db" in out for out in outputs)
