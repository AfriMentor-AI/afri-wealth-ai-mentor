#!/usr/bin/env bash
# Deploy the services that have shipped a real v1 so far to the staging overlay
# (card O2.1). See docs/deployment/staging.md for what "staging" means at this stage.
#
# Usage: scripts/deploy-staging.sh
# Env:   requires infra/keys/jwt_private_key.pem + jwt_public_key.pem (see
#        docs/deployment/staging.md §"RS256 keys" for how to generate them once).
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.staging.yml -p afrimentor-staging"

if [ ! -f infra/keys/jwt_private_key.pem ] || [ ! -f infra/keys/jwt_public_key.pem ]; then
  echo "Missing infra/keys/jwt_private_key.pem / jwt_public_key.pem — see" >&2
  echo "docs/deployment/staging.md before running this script." >&2
  exit 1
fi

echo "==> Building and starting the staging stack (api-gateway, auth-user-service + deps)"
$COMPOSE up -d --build api-gateway auth-user-service

echo "==> Waiting for services to report healthy"
for svc in postgres redis auth-user-service api-gateway; do
  healthy=""
  for _ in $(seq 1 30); do
    if $COMPOSE ps "$svc" | grep -qi "(healthy)"; then
      healthy=1
      break
    fi
    sleep 2
  done
  if [ -z "$healthy" ]; then
    echo "$svc did not become healthy in time" >&2
    $COMPOSE logs --tail 50 "$svc" >&2
    exit 1
  fi
  echo "  $svc: healthy"
done

echo "==> Smoke test: gateway health + signup/login round trip"
GATEWAY=http://localhost:8000
curl -fsS "$GATEWAY/health" | grep -q '"status":"healthy"'

EMAIL="staging-smoke-$(date +%s)@example.com"
SIGNUP=$(curl -fsS -X POST "$GATEWAY/api/v1/auth/signup" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"smoketestpass1\"}")
echo "$SIGNUP" | grep -q access_token

LOGIN=$(curl -fsS -X POST "$GATEWAY/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"smoketestpass1\"}")
echo "$LOGIN" | grep -q access_token

echo "==> Staging deploy OK — gateway on $GATEWAY, auth-user-service reachable via gateway and directly on :8001"
