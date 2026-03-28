# db_backup.py
"""
Database backup endpoint.

Uses mongodump to create a gzipped BSON backup of the live MongoDB database,
restorable with mongorestore --gzip.
"""

import os
import stat
import tempfile
import asyncio
import logging
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db_connector.settings import MongoDBSettings
from .dependencies import get_db_settings

logger = logging.getLogger(__name__)
router = APIRouter()


class BackupRequest(BaseModel):
    output_dir: str


class BackupResponse(BaseModel):
    success: bool
    backup_dir: str
    message: str
    duration_ms: float


@router.post("/backup-database", response_model=BackupResponse)
async def backup_database(
    request: BackupRequest,
    settings: MongoDBSettings = Depends(get_db_settings)
):
    """
    Backup the live MongoDB database using mongodump.

    Creates a timestamped subdirectory with gzipped BSON files, restorable
    with `mongorestore --gzip --dir <backup_dir>`.

    Request: { output_dir: str }
    Response: { success: bool, backup_dir: str, message: str, duration_ms: float }
    """
    start_time = datetime.now(timezone.utc)

    try:
        # 1. Validate output_dir
        real_path = os.path.realpath(request.output_dir)
        if not os.path.isdir(real_path):
            raise HTTPException(
                status_code=400,
                detail="output_dir does not exist or is not a directory"
            )
        if not os.access(real_path, os.W_OK):
            raise HTTPException(status_code=400, detail="output_dir is not writable")

        # 2. Resolve mongodump binary path
        mongodump_path = os.path.expanduser("~/.nlm/bin/mongodump")
        if not os.path.isfile(mongodump_path):
            raise HTTPException(
                status_code=500,
                detail=f"mongodump binary not found at {mongodump_path}. "
                        "Run 'npm run prepare:mongo' in front_end/ to download MongoDB tools."
            )

        # 3. Create timestamped subdirectory name
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_subdir = os.path.join(real_path, f"nlm_backup_{timestamp}")

        # 4. Write connection URI to temp config file (keeps credentials off process listing)
        uri_cfg = f'uri: "{settings.mongodb_connection_string}"\n'
        cfg_fd = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False, prefix='nlm_backup_'
        )
        cfg_fd.write(uri_cfg)
        cfg_fd.close()
        os.chmod(cfg_fd.name, stat.S_IRUSR)  # owner-read only (0o400)

        try:
            # 5. Build mongodump command
            cmd = [
                mongodump_path,
                f"--config={cfg_fd.name}",
                f"--db={settings.database_name}",
                "--gzip",
                f"--out={backup_subdir}",
            ]

            logger.info(f"Starting backup to {backup_subdir}")

            # 6. Run mongodump with timeout
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=600
                    )
                except asyncio.TimeoutError:
                    # Kill the process on timeout
                    logger.error(f"Backup timeout (600s) for {backup_subdir}")
                    proc.kill()
                    await proc.wait()
                    # Clean up partial backup
                    shutil.rmtree(backup_subdir, ignore_errors=True)
                    raise HTTPException(
                        status_code=500,
                        detail="Backup timed out after 600 seconds"
                    )

            except asyncio.CancelledError:
                # Process was cancelled
                proc.kill()
                await proc.wait()
                shutil.rmtree(backup_subdir, ignore_errors=True)
                raise HTTPException(
                    status_code=500,
                    detail="Backup operation was cancelled"
                )

        finally:
            os.unlink(cfg_fd.name)  # always clean up temp config file

        # 6. Check return code
        if proc.returncode != 0:
            # mongodump failed — clean up partial backup
            stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
            shutil.rmtree(backup_subdir, ignore_errors=True)
            logger.error(f"mongodump failed with code {proc.returncode}: {stderr_text}")
            raise HTTPException(
                status_code=500,
                detail=f"Backup failed: {stderr_text}"
            )

        # 7. Success
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        message = f"Backup completed successfully to {backup_subdir}"
        logger.info(f"{message} (duration: {duration_ms:.0f}ms)")

        return BackupResponse(
            success=True,
            backup_dir=backup_subdir,
            message=message,
            duration_ms=duration_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup failed with unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Backup failed: {str(e)}"
        )
