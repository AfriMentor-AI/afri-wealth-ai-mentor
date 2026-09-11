#!/bin/sh
# Applies pending Alembic migrations before the app starts (card O3.2).
# Mirrors auth-user-service's docker-entrypoint.sh pattern.
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
