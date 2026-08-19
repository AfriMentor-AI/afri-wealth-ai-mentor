#!/usr/bin/env bash
# Restore one or all service databases from a backup-postgres.sh output
# directory (card O4.5). Restores into the *same* database name it was
# dumped from — point this at a disposable/staging Postgres instance for a
# drill, never at a production one without a deliberate reason.
#
# Usage:
#   scripts/backup/restore-postgres.sh <backup-dir> [project-name] [db-name]
#   db-name restores just that one database; omit it to restore every dump
#   found in the backup directory.
set -euo pipefail
cd "$(dirname "$0")/../.."

BACKUP_DIR="${1:?Usage: restore-postgres.sh <backup-dir> [project-name] [db-name]}"
PROJECT="${2:-afrimentor}"
SINGLE_DB="${3:-}"
CONTAINER="${PROJECT}-postgres-1"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Postgres container '$CONTAINER' is not running (project '$PROJECT')." >&2
  exit 1
fi

restore_one() {
  local dump_file="$1"
  local db
  db="$(basename "$dump_file" .dump)"
  echo "  restoring $db from $dump_file"
  # --clean drops existing objects first so a restore onto a non-empty
  # database (e.g. re-running a drill) doesn't fail on "already exists".
  docker exec -i "$CONTAINER" pg_restore -U afrimentor --clean --if-exists --no-owner -d "$db" < "$dump_file"
}

echo "==> Restoring into project '$PROJECT' from $BACKUP_DIR"

if [ -n "$SINGLE_DB" ]; then
  restore_one "$BACKUP_DIR/${SINGLE_DB}.dump"
else
  for f in "$BACKUP_DIR"/*.dump; do
    restore_one "$f"
  done
fi

echo "==> Restore complete."
