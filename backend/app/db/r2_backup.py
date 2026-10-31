"""
DB backup/restore via S3-compatible storage (Backblaze B2 or Cloudflare R2).

Backs up all 3 SQLite WAL files:
    trading.db, trading.db-shm, trading.db-wal

Required env vars:
    BACKUP_BUCKET_NAME       — bucket name
    BACKUP_KEY_ID            — B2 application key ID  (or R2 Access Key ID)
    BACKUP_APP_KEY           — B2 application key     (or R2 Secret Access Key)
    BACKUP_ENDPOINT_URL      — e.g. https://s3.us-west-004.backblazeb2.com
                               or    https://<accountId>.r2.cloudflarestorage.com
    BACKUP_INTERVAL_MINUTES  — periodic upload interval, default: 60

All vars optional — if BACKUP_BUCKET_NAME is unset the module is a no-op.
"""

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_BUCKET   = os.getenv("BACKUP_BUCKET_NAME", "")
_KEY_ID   = os.getenv("BACKUP_KEY_ID", "")
_APP_KEY  = os.getenv("BACKUP_APP_KEY", "")
_ENDPOINT = os.getenv("BACKUP_ENDPOINT_URL", "")
_INTERVAL = int(os.getenv("BACKUP_INTERVAL_MINUTES", "60"))

_DB_PATH = Path(__file__).resolve().parents[2] / "trading.db"

# All 3 SQLite WAL files → their bucket object keys
_FILES = {
    _DB_PATH:                          "trading.db",
    Path(str(_DB_PATH) + "-shm"):      "trading.db-shm",
    Path(str(_DB_PATH) + "-wal"):      "trading.db-wal",
}


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


def _checkpoint():
    """
    Run WAL checkpoint so trading.db is fully up-to-date before upload.
    This flushes all WAL pages into the main DB file, making the backup
    consistent even if only trading.db is restored.
    """
    if not _DB_PATH.exists():
        return
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        logger.debug("WAL checkpoint completed before backup")
    except Exception as e:
        logger.warning("WAL checkpoint failed (backup may be slightly stale): %s", e)


def backup_to_r2() -> bool:
    """Checkpoint WAL then upload trading.db + .shm + .wal to bucket."""
    if not _configured():
        logger.debug("Backup skipped — BACKUP_BUCKET_NAME not configured")
        return False
    if not _DB_PATH.exists():
        logger.warning("Backup skipped — DB file not found: %s", _DB_PATH)
        return False

    _checkpoint()

    client = _client()
    uploaded = []
    for local_path, object_key in _FILES.items():
        if not local_path.exists():
            logger.debug("Skipping %s — file not present", local_path.name)
            continue
        try:
            client.upload_file(str(local_path), _BUCKET, object_key)
            size_kb = local_path.stat().st_size / 1024
            uploaded.append(f"{object_key} ({size_kb:.1f} KB)")
        except Exception as e:
            logger.error("❌ Failed to upload %s: %s", object_key, e)
            return False

    logger.info("✅ DB backed up: %s", ", ".join(uploaded))
    return True


def restore_from_r2() -> bool:
    """
    Download trading.db (+ .shm + .wal) from bucket on startup.
    Only restores if remote trading.db is newer than local, or local is missing.
    """
    if not _configured():
        logger.debug("Restore skipped — BACKUP_BUCKET_NAME not configured")
        return False

    client = _client()

    # Check remote trading.db timestamp first
    try:
        head = client.head_object(Bucket=_BUCKET, Key="trading.db")
        remote_mtime = head["LastModified"].timestamp()
    except Exception as e:
        logger.info("No remote backup found or unreachable (%s) — starting fresh", e)
        return False

    if _DB_PATH.exists():
        local_mtime = _DB_PATH.stat().st_mtime
        if local_mtime >= remote_mtime:
            logger.info("✅ Local DB is up-to-date, skipping restore")
            return False

    # Download all 3 files
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    restored = []
    for local_path, object_key in _FILES.items():
        try:
            client.download_file(_BUCKET, object_key, str(local_path))
            size_kb = local_path.stat().st_size / 1024
            restored.append(f"{object_key} ({size_kb:.1f} KB)")
        except Exception:
            logger.debug("Remote file %s not found — skipping", object_key)

    if restored:
        logger.info("✅ DB restored from bucket: %s", ", ".join(restored))
        return True
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
