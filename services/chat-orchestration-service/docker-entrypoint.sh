#!/bin/sh
# Applies pending Alembic migrations before the app starts (mirrors
# auth-user-service, card O2.1). `init_db()` in app/database.py still runs
# create_all() as a dev/test bootstrap fallback, but Alembic is the real,
# versioned schema history for staging/prod.
set -e

MAX_RETRIES=30
RETRY_COUNT=0
until alembic upgrade head; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: Alembic migration failed after $MAX_RETRIES attempts. Giving up."
        exit 1
    fi
    echo "WARNING: Alembic migration failed (attempt $RETRY_COUNT/$MAX_RETRIES). Retrying in 5s..."
    sleep 5
done

exec "$@"