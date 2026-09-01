"""
Unit tests for db_connector.auth_probe: the tri-state fail-closed enforcement
probe (R2) and the loopback() host classifier (R3).

The probe's MongoClient is mocked so all four outcome arms can be forced
deterministically without a live mongod.
"""

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError

import db_connector.auth_probe as auth_probe
from db_connector.auth_probe import AuthEnforcementError, loopback, verify_auth_enforced
from db_connector.settings import MongoDBSettings


def _settings(uri: str) -> MongoDBSettings:
    return MongoDBSettings(mongodb_connection_string=uri, database_name="testdb")


def _mock_client_raising(exc):
    client = MagicMock()
    client.__getitem__.return_value.list_collection_names.side_effect = exc
    return client


def _mock_client_succeeding():
    client = MagicMock()
    client.__getitem__.return_value.list_collection_names.return_value = []
    return client


# ─── R3 — loopback() classification (E13: literal "localhost" must qualify) ──

class TestLoopback:
    @pytest.mark.parametrize("uri", [
        "mongodb://localhost:27019/",
        "mongodb://127.0.0.1:27019/",
        "mongodb://127.5.5.5:27019/",
        "mongodb://[::1]:27019/",
        "mongodb://nlm_app:pw@localhost:27019/?authSource=admin",
    ])
    def test_loopback_hosts(self, uri):
        assert loopback(uri) is True

    @pytest.mark.parametrize("uri", [
        "mongodb://example.com:27019/",
        "mongodb://10.0.0.5:27019/",
        "mongodb://192.168.1.10:27019/",
        "mongodb+srv://cluster0.mongodb.net/",
    ])
    def test_non_loopback_hosts(self, uri):
        assert loopback(uri) is False

    def test_multi_host_all_must_qualify(self):
        assert loopback("mongodb://localhost:27017,10.0.0.5:27018/") is False


# ─── R2 — the four probe arms ────────────────────────────────────────────────

class TestProbeArms:
    @pytest.mark.parametrize("code", [13, 18])
    def test_auth_enforced_codes_pass(self, code):
        client = _mock_client_raising(OperationFailure("denied", code))
        with patch.object(auth_probe, "MongoClient", return_value=client):
            verify_auth_enforced(_settings("mongodb://127.0.0.1:27019/"))  # returns normally
        client.close.assert_called_once()

    def test_success_is_fatal(self):
        client = _mock_client_succeeding()
        with patch.object(auth_probe, "MongoClient", return_value=client):
            with pytest.raises(AuthEnforcementError):
                verify_auth_enforced(_settings("mongodb://127.0.0.1:27019/"))
        client.close.assert_called_once()

    @pytest.mark.parametrize("exc", [
        ConnectionFailure("down"),
        ServerSelectionTimeoutError("no server"),
    ])
    def test_mongod_down_is_inconclusive_and_propagates(self, exc):
        client = _mock_client_raising(exc)
        with patch.object(auth_probe, "MongoClient", return_value=client):
            with pytest.raises((ConnectionFailure, ServerSelectionTimeoutError)):
                verify_auth_enforced(_settings("mongodb://127.0.0.1:27019/"))
        # Not an AuthEnforcementError — this is the DB-unavailable path.
        client.close.assert_called_once()

    def test_other_operation_failure_code_is_fatal(self):
        # Any code other than 13/18 is unexplained → fail closed. It propagates
        # as OperationFailure (not wrapped), which is fatal upstream.
        client = _mock_client_raising(OperationFailure("weird", 40415))
        with patch.object(auth_probe, "MongoClient", return_value=client):
            with pytest.raises(OperationFailure):
                verify_auth_enforced(_settings("mongodb://127.0.0.1:27019/"))
        client.close.assert_called_once()


# ─── Loopback-only: off-loopback skips the probe entirely ────────────────────

class TestLoopbackSkip:
    def test_non_loopback_skips_without_connecting(self):
        with patch.object(auth_probe, "MongoClient") as MockClient:
            verify_auth_enforced(_settings("mongodb://example.com:27019/"))
            MockClient.assert_not_called()  # no client constructed, no DNS, no probe
