"""
Tests for the FastAPI lifespan's startup auth gate and schema-enforcement hook
in main.py.

The gate is two-sided and both sides are fatal:
- The anonymous probe (verify_auth_enforced) proves mongod enforces auth.
- The authenticated connect (get_mongodb_connector) proves OUR credential works.
A credential that is absent/stale surfaces as OperationFailure 13/18 and must
raise AuthEnforcementError carrying the migration guidance — not fall into the
non-fatal schema-enforcement handler.

Schema enforcement stays non-fatal: it logs and the app continues.

These tests call `main.lifespan(main.app)` directly rather than going through
httpx's ASGITransport, since ASGITransport does not trigger the ASGI lifespan
protocol without an explicit lifespan manager.

verify_auth_enforced is stubbed by an autouse fixture so tests that aren't
about the probe don't perform real I/O against the session mongod; tests that
are about it re-patch it locally.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError

import main
from db_connector.auth_probe import AuthEnforcementError


@pytest.fixture(autouse=True)
def _stub_auth_probe(monkeypatch):
    # Default: the anonymous enforcement probe passes and does no real I/O.
    # Tests that exercise the probe override this with patch.object.
    monkeypatch.setattr(main, "verify_auth_enforced", MagicMock(return_value=None))


class _FakeReport:
    def summary(self):
        return "=== fake schema enforcement report ==="


class TestLifespanHappyPath:
    @pytest.mark.asyncio
    async def test_enforce_called_in_enforce_mode_and_summary_logged(self, caplog):
        fake_db = MagicMock()
        fake_report = _FakeReport()

        with patch.object(
            main, "get_mongodb_connector", new=AsyncMock(return_value=fake_db)
        ), patch.object(main, "SchemaEnforcer") as MockEnforcer:
            MockEnforcer.return_value.enforce = AsyncMock(return_value=fake_report)

            with caplog.at_level("INFO"):
                async with main.lifespan(main.app):
                    pass

            MockEnforcer.assert_called_once_with(fake_db, dry_run=False)
            MockEnforcer.return_value.enforce.assert_awaited_once()
            assert any(
                "fake schema enforcement report" in rec.message for rec in caplog.records
            )


class TestAuthGateFatal:
    """The two fatal sides of the gate (Verification Step 6)."""

    @pytest.mark.asyncio
    async def test_auth_not_enforced_escapes_lifespan(self):
        # Enforcement side: mongod isn't enforcing auth → AuthEnforcementError.
        with patch.object(
            main, "verify_auth_enforced",
            new=MagicMock(side_effect=AuthEnforcementError("not enforcing")),
        ), patch.object(main, "get_mongodb_connector", new=AsyncMock()):
            with pytest.raises(AuthEnforcementError):
                async with main.lifespan(main.app):
                    pass

    @pytest.mark.asyncio
    async def test_stale_credential_escapes_with_migration_message(self):
        # Credential side: probe passes (auth on), but our stored credential
        # gets 13 → fatal, and the raised message is the migration guidance.
        with patch.object(
            main, "get_mongodb_connector",
            new=AsyncMock(side_effect=OperationFailure("unauthorized", 13)),
        ):
            with pytest.raises(AuthEnforcementError) as exc:
                async with main.lifespan(main.app):
                    pass

            assert "python -m db_connector.setup_auth" in str(exc.value)

    @pytest.mark.asyncio
    async def test_unknown_operation_failure_is_fatal(self):
        # Any other OperationFailure code is unexplained — fail closed. It is
        # re-raised as-is, not wrapped, and is not AuthEnforcementError.
        with patch.object(
            main, "get_mongodb_connector",
            new=AsyncMock(side_effect=OperationFailure("weird", 999)),
        ):
            with pytest.raises(OperationFailure):
                async with main.lifespan(main.app):
                    pass

    @pytest.mark.asyncio
    async def test_probe_timeout_is_fatal(self):
        # A timeout on either auth operation means the verdict is UNKNOWN,
        # which must fail closed.
        async def _fake_wait_for(coro, timeout):
            if timeout == main.AUTH_BUDGET_S:
                coro.close()
                raise asyncio.TimeoutError()
            return await coro

        with patch.object(main.asyncio, "wait_for", new=_fake_wait_for):
            with pytest.raises(AuthEnforcementError):
                async with main.lifespan(main.app):
                    pass


class TestLifespanNonFatal:
    @pytest.mark.asyncio
    async def test_mongod_down_is_non_fatal(self, caplog):
        # mongod being down is the one connector failure that stays non-fatal:
        # connector stays None, schema enforcement is skipped, app still starts.
        with patch.object(
            main, "get_mongodb_connector",
            new=AsyncMock(side_effect=ServerSelectionTimeoutError("mongod down")),
        ), patch.object(main, "SchemaEnforcer") as MockEnforcer:
            async with main.lifespan(main.app):
                pass  # must not raise

            MockEnforcer.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_failure_is_non_fatal(self):
        with patch.object(
            main, "get_mongodb_connector",
            new=AsyncMock(side_effect=ConnectionFailure("refused")),
        ), patch.object(main, "SchemaEnforcer") as MockEnforcer:
            async with main.lifespan(main.app):
                pass  # must not raise

            MockEnforcer.assert_not_called()

    @pytest.mark.asyncio
    async def test_enforce_exception_is_caught_and_logged(self, caplog):
        fake_db = MagicMock()

        with patch.object(
            main, "get_mongodb_connector", new=AsyncMock(return_value=fake_db)
        ), patch.object(main, "SchemaEnforcer") as MockEnforcer:
            MockEnforcer.return_value.enforce = AsyncMock(side_effect=RuntimeError("boom"))

            with caplog.at_level("ERROR"):
                async with main.lifespan(main.app):
                    pass

            assert any(
                "schema enforcement failed at startup (non-fatal)" in rec.message
                for rec in caplog.records
            )

    @pytest.mark.asyncio
    async def test_enforce_timeout_is_caught_and_logged(self, caplog):
        # Narrowed to the enforcement call: the fake only fires on the
        # ENFORCE_BUDGET_S wait_for, letting the two AUTH_BUDGET_S auth
        # operations run normally. Exceeding the enforce budget is non-fatal.
        fake_db = MagicMock()

        async def _fake_wait_for(coro, timeout):
            if timeout == main.ENFORCE_BUDGET_S:
                coro.close()
                raise asyncio.TimeoutError()
            return await coro

        with patch.object(
            main, "get_mongodb_connector", new=AsyncMock(return_value=fake_db)
        ), patch.object(main, "SchemaEnforcer") as MockEnforcer, patch.object(
            main.asyncio, "wait_for", new=_fake_wait_for
        ):
            MockEnforcer.return_value.enforce = AsyncMock(return_value=_FakeReport())

            with caplog.at_level("ERROR"):
                async with main.lifespan(main.app):
                    pass

            assert any(
                "schema enforcement failed at startup (non-fatal)" in rec.message
                for rec in caplog.records
            )
