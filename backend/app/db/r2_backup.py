"""
DB backup/restore via S3-compatible storage (Backblaze B2 or Cloudflare R2).

Required env vars:
    BACKUP_BUCKET_NAME       — bucket name
    BACKUP_KEY_ID            — B2 application key ID  (or R2 Access Key ID)
    BACKUP_APP_KEY           — B2 application key     (or R2 Secret Access Key)
    BACKUP_ENDPOINT_URL      — e.g. https://<accountId>.r2.cloudflarestorage.com
                               or    https://s3.us-west-004.backblazeb2.com
    BACKUP_OBJECT_KEY        — object name in bucket, default: trading.db
    BACKUP_INTERVAL_MINUTES  — periodic upload interval, default: 60

All vars optional — if BACKUP_BUCKET_NAME is unset the module is a no-op.
"""

import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_BUCKET      = os.getenv("BACKUP_BUCKET_NAME", "")
_KEY_ID      = os.getenv("BACKUP_KEY_ID", "")
_APP_KEY     = os.getenv("BACKUP_APP_KEY", "")
_ENDPOINT    = os.getenv("BACKUP_ENDPOINT_URL", "")
_OBJECT_KEY  = os.getenv("BACKUP_OBJECT_KEY", "trading.db")
_INTERVAL    = int(os.getenv("BACKUP_INTERVAL_MINUTES", "60"))

_DB_PATH = Path(__file__).resolve().parents[2] / "trading.db"


def _client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_KEY_ID,
        aws_secret_access_key=_APP_KEY,
    )


def _configured() -> bool:
    return bool(_BUCKET and _KEY_ID and _APP_KEY and _ENDPOINT)


def backup_to_r2() -> bool:
    """Upload trading.db to bucket. Returns True on success."""
    if not _configured():
        logger.debug("Backup skipped — BACKUP_BUCKET_NAME not configured")
        return False
    if not _DB_PATH.exists():
        logger.warning("Backup skipped — DB file not found: %s", _DB_PATH)
        return False
    try:
        _client().upload_file(str(_DB_PATH), _BUCKET, _OBJECT_KEY)
        size_mb = _DB_PATH.stat().st_size / 1_048_576
        logger.info("✅ DB backed up to %s/%s (%.2f MB)", _BUCKET, _OBJECT_KEY, size_mb)
        return True
    except Exception as e:
        logger.error("❌ DB backup failed: %s", e)
        return False


def restore_from_r2() -> bool:
    """Download trading.db from bucket if local file is missing or older. Returns True on success."""
    if not _configured():
        logger.debug("Restore skipped — BACKUP_BUCKET_NAME not configured")
        return False
    try:
        client = _client()
        head = client.head_object(Bucket=_BUCKET, Key=_OBJECT_KEY)
        remote_mtime = head["LastModified"].timestamp()

        if _DB_PATH.exists():
            local_mtime = _DB_PATH.stat().st_mtime
            if local_mtime >= remote_mtime:
                logger.info("✅ Local DB is up-to-date, skipping restore")
                return False

        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(_BUCKET, _OBJECT_KEY, str(_DB_PATH))
        size_mb = _DB_PATH.stat().st_size / 1_048_576
        logger.info("✅ DB restored from %s/%s (%.2f MB)", _BUCKET, _OBJECT_KEY, size_mb)
        return True
    except client.exceptions.NoSuchKey:
        logger.info("No remote backup found at %s/%s — starting fresh", _BUCKET, _OBJECT_KEY)
        return False
    except Exception as e:
        logger.warning("DB restore failed (non-fatal): %s", e)
        return False


def _periodic_backup_loop():
    interval_sec = _INTERVAL * 60
    logger.info("🔄 Periodic DB backup started (every %d min)", _INTERVAL)
    while True:
        time.sleep(interval_sec)
        backup_to_r2()


def start_periodic_backup():
    """Start background thread that uploads DB every BACKUP_INTERVAL_MINUTES."""
    if not _configured():
        return
    t = threading.Thread(target=_periodic_backup_loop, name="db-backup", daemon=True)
    t.start()
