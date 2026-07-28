#!/bin/bash
# Creates one database per service on first Postgres boot (O1.2 / ADR-0001 D2).
set -e
DBS="svc_auth svc_intake svc_chat svc_persona svc_rag svc_goals svc_progress svc_insight svc_feedback svc_research svc_voice svc_notify"
for db in $DBS; do
  echo "  creating database $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done
echo "all service databases ensured"
