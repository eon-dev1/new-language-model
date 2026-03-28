"""
Tests for db_backup.py — verify credentials don't leak to process listing.
Tests the actual contract: --uri= must not appear in subprocess args.
"""
import pytest
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
