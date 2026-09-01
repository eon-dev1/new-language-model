"""
Tests for db_backup.py — verify credentials don't leak to process listing,
and that a failed mongodump doesn't echo its stderr back to the client.
"""
import pytest
from fastapi import HTTPException
from unittest.mock import patch, AsyncMock, MagicMock


class TestBackupCredentialHandling:
    """Verify mongodump receives credentials via config file, not CLI args."""

    @pytest.mark.asyncio
    async def test_mongodump_cmd_has_no_uri_and_uses_config(self):
        """--uri= must not appear in args; --config= must appear instead."""
        captured_cmd = []

        async def fake_subprocess(*cmd, **kwargs):
            captured_cmd.extend(cmd)
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0
            proc.kill = MagicMock()
            proc.wait = AsyncMock()
            return proc

        mock_settings = MagicMock()
        mock_settings.mongodb_connection_string = "mongodb://user:secret@host/db"
        mock_settings.database_name = "nlm_db"

        with patch("routes.db_backup.asyncio.create_subprocess_exec", side_effect=fake_subprocess), \
             patch("routes.db_backup.os.path.isfile", return_value=True), \
             patch("routes.db_backup.os.path.isdir", return_value=True), \
             patch("routes.db_backup.os.access", return_value=True), \
             patch("routes.db_backup.os.path.realpath", side_effect=lambda p: p):

            from routes.db_backup import BackupRequest, backup_database

            request = BackupRequest(output_dir="/tmp/test_backup")
            await backup_database(request, settings=mock_settings)

            # Key assertions: no --uri= leaked, --config= used instead
            for arg in captured_cmd:
                assert not str(arg).startswith("--uri="), \
                    f"Credentials leaked in CLI arg: {arg}"

            config_args = [a for a in captured_cmd if str(a).startswith("--config=")]
            assert len(config_args) == 1, \
                f"Expected --config= flag, got args: {captured_cmd}"

    @pytest.mark.asyncio
    async def test_mongodump_failure_does_not_leak_stderr(self):
        """A failed mongodump must not echo its stderr (db name, temp config path) to the client."""
        stderr_sentinel = b"SENTINEL_STDERR: connecting to mongodb://user:secret@host/nlm_translator"

        async def fake_subprocess(*cmd, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"", stderr_sentinel))
            proc.returncode = 1
            proc.kill = MagicMock()
            proc.wait = AsyncMock()
            return proc

        mock_settings = MagicMock()
        mock_settings.mongodb_connection_string = "mongodb://user:secret@host/db"
        mock_settings.database_name = "nlm_db"

        with patch("routes.db_backup.asyncio.create_subprocess_exec", side_effect=fake_subprocess), \
             patch("routes.db_backup.os.path.isfile", return_value=True), \
             patch("routes.db_backup.os.path.isdir", return_value=True), \
             patch("routes.db_backup.os.access", return_value=True), \
             patch("routes.db_backup.os.path.realpath", side_effect=lambda p: p), \
             patch("routes.db_backup.shutil.rmtree"):

            from routes.db_backup import BackupRequest, backup_database

            request = BackupRequest(output_dir="/tmp/test_backup")
            with pytest.raises(HTTPException) as exc_info:
                await backup_database(request, settings=mock_settings)

            assert "SENTINEL_STDERR" not in exc_info.value.detail
            assert exc_info.value.detail == "Backup failed"
