#!/usr/bin/env bash
# Deploy a git tag/commit on the production VM, with automatic rollback when the health check fails.
#   cd /opt/baixeai && scripts/deploy.sh v1.0.0
# Order: build new images -> encrypted backup -> migrations -> restart -> health check -> (rollback).
# Migrations must be backward compatible (expand -> migrate -> contract), so the previous version still runs
# on the migrated schema if a rollback is needed. A destructive migration needs a same-day backup (taken here).
set -euo pipefail

REF=${1:?usage: scripts/deploy.sh <git tag or commit>}
cd "$(dirname "$0")/.."
C=(docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env)
DOMAIN=$(grep -E '^SITE_DOMAIN=' .env | cut -d= -f2-)
PREV=$(git rev-parse HEAD)
log() { echo "[$(date -u +%FT%TZ)] $*"; }

healthy() {
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 "https://$DOMAIN/healthz" >/dev/null && curl -fsS --max-time 5 "https://$DOMAIN/" >/dev/null; then
      return 0
    fi
    sleep 5
  done
  return 1
}

log "fetching $REF (current: $PREV)"
git fetch --tags --quiet origin
git checkout --quiet --detach "$REF"

log "building images"
"${C[@]}" build --pull

log "backup before migrating"
"${C[@]}" run --rm backup once

log "migrating + seeding catalog"
"${C[@]}" up -d --wait db redis
"${C[@]}" run --rm migrate

log "restarting services"
"${C[@]}" up -d --remove-orphans

if healthy; then
  echo "$(date -u +%FT%TZ) $REF $(git rev-parse --short HEAD)" >> deploy-history.log
  log "deploy OK: $REF"
  exit 0
fi

log "HEALTH CHECK FAILED -> rolling back to $PREV"
git checkout --quiet --detach "$PREV"
"${C[@]}" build
"${C[@]}" up -d --remove-orphans
healthy && log "rollback OK (now on $PREV). Investigate: docker compose logs api frontend" \
        || log "ROLLBACK ALSO UNHEALTHY: follow docs/OPERACAO.md 'Incidente: site fora do ar'"
exit 1
