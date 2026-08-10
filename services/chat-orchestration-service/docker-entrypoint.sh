#!/bin/sh
# Applies pending Alembic migrations before the app starts (mirrors
# auth-user-service, card O2.1). `init_db()` in app/database.py still runs
# create_all() as a dev/test bootstrap fallback, but Alembic is the real,
# versioned schema history for staging/prod.
set -e
alembic upgrade head
exec "$@"
