#!/usr/bin/env bash
# Dump every service's Postgres database to a timestamped local directory
# (card O4.5). One shared Postgres instance holds one database per service
# (see infra/postgres/init-databases.sh) — this backs each one up separately
# so a single service can be restored without touching the others.
#
# Usage: scripts/backup/backup-postgres.sh [project-name] [out-dir]
#   project-name defaults to "afrimentor" (the dev stack); pass
#   "afrimentor-staging" to back up the staging stack instead.
#   out-dir defaults to ./backups/<timestamp>/
set -euo pipefail
cd "$(dirname "$0")/../.."

PROJECT="${1:-afrimentor}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${2:-backups/${TIMESTAMP}}"
CONTAINER="${PROJECT}-postgres-1"

DBS="svc_auth svc_intake svc_chat svc_persona svc_rag svc_goals svc_progress svc_insight svc_feedback svc_research svc_voice svc_notify svc_mlflow"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Postgres container '$CONTAINER' is not running (project '$PROJECT')." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
echo "==> Backing up project '$PROJECT' to $OUT_DIR"

for db in $DBS; do
  echo "  dumping $db"
  docker exec "$CONTAINER" pg_dump -U afrimentor --format=custom "$db" > "$OUT_DIR/${db}.dump"
done

echo "==> Done. $(ls "$OUT_DIR" | wc -l) database dumps written to $OUT_DIR"
