#!/bin/bash
# ─────────────────────────────────────────────────────────────
# FastTrade DB Backup & Restore
# Usage:
#   ./db_backup.sh backup          → dumps DB to ./backups/
#   ./db_backup.sh restore <file>  → restores from a dump file
# ─────────────────────────────────────────────────────────────

set -e

CONTAINER="fasttrade-db"
DB_USER="fasttrade"
DB_NAME="fasttrade"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$BACKUP_DIR"

case "$1" in
  backup)
    FILE="$BACKUP_DIR/fasttrade_${TIMESTAMP}.sql"
    echo "📦 Backing up to $FILE ..."
    docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" > "$FILE"
    echo "✅ Backup saved: $FILE"
    ;;

  restore)
    FILE="$2"
    if [ -z "$FILE" ]; then
      echo "❌ Usage: ./db_backup.sh restore <backup_file.sql>"
      exit 1
    fi
    echo "♻️  Restoring from $FILE ..."
    # Drop and recreate the DB cleanly
    docker exec "$CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"
    docker exec "$CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"
    docker exec -i "$CONTAINER" psql -U "$DB_USER" "$DB_NAME" < "$FILE"
    echo "✅ Restore complete"
    ;;

  *)
    echo "Usage: ./db_backup.sh [backup|restore <file>]"
    exit 1
    ;;
esac
