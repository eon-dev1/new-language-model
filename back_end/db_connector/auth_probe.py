# db_connector/auth_probe.py
#
# Startup verification that mongod is actually enforcing --auth. Runs as an
# anonymous client — no stored credential — so a "pass" here says nothing
# about whether our own credential works. That is a separate question,
# answered by the authenticated connect the caller performs alongside this.

import ipaddress
import logging

from pymongo import MongoClient
from pymongo.errors import OperationFailure
from pymongo.uri_parser import parse_uri

from db_connector.settings import MongoDBSettings

logger = logging.getLogger(__name__)

SERVER_SELECTION_TIMEOUT_MS = 5000


class AuthEnforcementError(Exception):
    """Raised when mongod is not enforcing authentication, or the probe's
    outcome cannot be classified. str(self) is the user-facing message."""


def _host_is_loopback(host: str) -> bool:
    if host in ("localhost", "::1"):
        return True
    try:
        return ipaddress.IPv4Address(host) in ipaddress.IPv4Network("127.0.0.0/8")
    except ValueError:
        return False


def loopback(connection_string: str) -> bool:
    """True only if every host in the URI is loopback. mongodb+srv:// is
    never loopback and is rejected before parsing — constructing a client for
    one performs an eager DNS lookup, which is not this probe's job to pay for."""
    if connection_string.startswith("mongodb+srv://"):
        return False
    hosts = parse_uri(connection_string)["nodelist"]
    return all(_host_is_loopback(host) for host, _port in hosts)


def _anonymous_uri(connection_string: str) -> str:
    host, port = parse_uri(connection_string)["nodelist"][0]
    return f"mongodb://{host}:{port}/?authSource=admin"


def verify_auth_enforced(settings: MongoDBSettings | None = None) -> None:
    """Anonymously attempt a real read on the app database.

    Tri-state, fail-closed:
      - OperationFailure 13/18 (unauthorized/auth failed) -> pass, returns normally
      - the read succeeds                                 -> FATAL, raises
      - ConnectionFailure/ServerSelectionTimeoutError      -> inconclusive, propagates
        (mongod down; the caller's own DB-unavailable handling applies)
      - anything else, including any other OperationFailure code -> FATAL, propagates
    """
    settings = settings or MongoDBSettings.create_from_credentials()
    connection_string = settings.mongodb_connection_string

    if not loopback(connection_string):
        logger.info("MongoDB host is not loopback — auth enforcement was not verified.")
        return

    client = MongoClient(
        _anonymous_uri(connection_string),
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        directConnection=True,
    )
    try:
        client[settings.database_name].list_collection_names()
    except OperationFailure as e:
        if e.code in (13, 18):
            return
        raise
    else:
        raise AuthEnforcementError(
            "MongoDB is not enforcing authentication. Refusing to start — "
            "see README.md."
        )
    finally:
        client.close()
