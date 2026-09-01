# shared/logging_setup.py
# Process-wide logging setup: request-id tagging and credential redaction.

import logging
import re
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar('request_id', default='--------')

# Strips URI userinfo (`//user:pw@`) so a leaked connection string doesn't
# carry its credentials into a log line. A bare password with no `//...@`
# wrapper around it still passes through untouched.
_USERINFO_RE = re.compile(r"//[^/@\s]+@")


def redact(text: str) -> str:
    return _USERINFO_RE.sub("//", text)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _RedactingFormatter(logging.Formatter):
    # Traceback text is rendered inside the base Formatter.format() call
    # (via formatException), so wrapping its full output covers both the
    # message and the traceback in one pass.
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def install_logging() -> None:
    logging.basicConfig(level=logging.INFO)

    root_logger = logging.getLogger()
    request_id_filter = RequestIdFilter()
    formatter = _RedactingFormatter('%(levelname)s:%(name)s:[%(request_id)s] %(message)s')
    for handler in root_logger.handlers:
        handler.addFilter(request_id_filter)
        handler.setFormatter(formatter)
