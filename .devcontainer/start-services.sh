#!/usr/bin/env bash
set -euo pipefail

# start-services.sh
# Start optional services in batches to avoid overwhelming Codespaces resources.
# Run from the Codespaces terminal (inside the Codespace or on the host if you have docker access).

# Detect compose command
if command -v "docker" >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "Error: neither 'docker compose' nor 'docker-compose' found in PATH." >&2
  exit 1
fi

BASE_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$BASE_DIR"

# Helper: wait for a service to become healthy (or running if no healthcheck)
wait_for_health() {
  local svc="$1"
  local timeout=${2:-120}
  local interval=3
  local elapsed=0
  local cid status

  echo "Waiting for $svc to report healthy (timeout ${timeout}s)..."
  while [ $elapsed -lt $timeout ]; do
    cid=$($COMPOSE_CMD ps -q "$svc" 2>/dev/null || true)
    if [ -n "$cid" ]; then
      status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || true)
      echo "  $svc -> $status"
      if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
        return 0
      fi
    fi
    sleep $interval
    elapsed=$((elapsed + interval))
  done
  echo "Timed out waiting for $svc to be healthy" >&2
  return 1
}

# Ensure core services are up
CORE_SERVICES=(postgres redis rabbitmq auth-user-service api-gateway)
echo "Ensuring core services are up: ${CORE_SERVICES[*]}"
$COMPOSE_CMD up -d ${CORE_SERVICES[*]}

# Wait for core DB/broker health
wait_for_health postgres 180 || echo "Warning: postgres did not reach healthy state in time"
wait_for_health redis 60 || echo "Warning: redis did not reach healthy state in time"
wait_for_health rabbitmq 120 || echo "Warning: rabbitmq did not reach healthy state in time"

# Batch 1: Vector DB, ML tracking, RAG & persona services
BATCH1=(chromadb mlflow rag-corpus-service persona-prompt-service)
echo "Starting batch1: ${BATCH1[*]}"
$COMPOSE_CMD up -d ${BATCH1[*]}

# Wait a bit for batch1 to stabilize
for svc in "${BATCH1[@]}"; do
  wait_for_health "$svc" 120 || echo "Notice: $svc may not have health checks or failed to become healthy"
done

# Small cooldown to avoid spikes
echo "Cooldown 20s after batch1"
sleep 20

# Batch 2: remaining application services (workers, evaluation, notification, etc.)
BATCH2=(intake-profiling-service chat-orchestration-service goals-milestones-service progress-gamification-service insight-library-service feedback-service research-evaluation-service voice-service notification-service)
echo "Starting batch2: ${BATCH2[*]}"
$COMPOSE_CMD up -d ${BATCH2[*]}

for svc in "${BATCH2[@]}"; do
  wait_for_health "$svc" 120 || echo "Notice: $svc may not have health checks or failed to become healthy"
done

echo "All batches started. Inspect with: $COMPOSE_CMD ps"
