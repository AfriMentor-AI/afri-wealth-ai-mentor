#!/usr/bin/env bash
# Deploy the lean-MVP service set to a self-hosted free-tier VM (Oracle Cloud
# Always Free — see docs/deployment/oracle-free-tier.md). Run this ON the VM,
# after cloning the repo there.
#
# Same services as scripts/deploy-staging.sh, plus docker-compose.oracle.yml,
# which locks every service's port down except api-gateway's — this host has
# a public IP, that one doesn't.
#
# Usage: scripts/deploy-oracle.sh
# Env:   requires infra/keys/jwt_private_key.pem + jwt_public_key.pem (see
#        docs/deployment/staging.md §"RS256 keys") and a root .env with
#        LLM_API_KEY set (copy .env.example).
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.oracle.yml -p afrimentor-staging"

if [ ! -f infra/keys/jwt_private_key.pem ] || [ ! -f infra/keys/jwt_public_key.pem ]; then
  echo "Missing infra/keys/jwt_private_key.pem / jwt_public_key.pem — see" >&2
  echo "docs/deployment/staging.md before running this script." >&2
  exit 1
fi

if [ ! -f .env ] || ! grep -q '^LLM_API_KEY=' .env; then
  echo "Missing LLM_API_KEY in .env — copy .env.example to .env and fill it in." >&2
  exit 1
fi

echo "==> Building and starting the lean-MVP stack (api-gateway, auth-user-service, chat-orchestration-service, persona-prompt-service, rag-corpus-service)"
echo "    First run builds 5 images from scratch on a free-tier VM — expect this to take a while."
$COMPOSE up -d --build api-gateway auth-user-service chat-orchestration-service persona-prompt-service rag-corpus-service

echo "==> Waiting for services to report healthy"
# Longer timeout than deploy-staging.sh's (60 x 3s vs 30 x 2s) — a free-tier
# VM is slower to boot 9 containers than a dev machine.
for svc in postgres redis rabbitmq chromadb auth-user-service persona-prompt-service rag-corpus-service chat-orchestration-service api-gateway; do
  healthy=""
  for _ in $(seq 1 60); do
    if $COMPOSE ps "$svc" | grep -qi "(healthy)"; then
      healthy=1
      break
    fi
    sleep 3
  done
  if [ -z "$healthy" ]; then
    echo "$svc did not become healthy in time" >&2
    $COMPOSE logs --tail 80 "$svc" >&2
    exit 1
  fi
  echo "  $svc: healthy"
done

echo "==> Smoke test: gateway health + signup/login round trip"
GATEWAY=http://localhost:8000
curl -fsS "$GATEWAY/health" | grep -q '"status":"healthy"'

EMAIL="oracle-smoke-$(date +%s)@example.com"
SIGNUP=$(curl -fsS -X POST "$GATEWAY/api/v1/auth/signup" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"smoketestpass1\"}")
echo "$SIGNUP" | grep -q access_token

LOGIN=$(curl -fsS -X POST "$GATEWAY/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"smoketestpass1\"}")
echo "$LOGIN" | grep -q access_token

PUBLIC_IP="$(curl -fsS --max-time 3 ifconfig.me || echo '<your-vm-public-ip>')"
echo "==> Deploy OK — gateway reachable locally on $GATEWAY."
echo "    From the internet: http://$PUBLIC_IP:8000 — only once the OCI Security"
echo "    List AND the host iptables both allow inbound TCP 8000 (see"
echo "    docs/deployment/oracle-free-tier.md, both are required)."
