#!/usr/bin/env bash
# Restore drill: decrypt a backup, restore it into a FRESH, isolated PostgreSQL and verify it.
# A backup only counts once this passes (docs/architecture/10 §4). Run monthly and after schema changes.
#
#   scripts/restore-test.sh <backup.dump.age> <age-identity-file> [source-compose-db-for-row-comparison]
#
# Checks: pg_restore without errors; same tables; append-only ledger trigger present; ledger sums match the
# wallet counters (the same reconciliation the app runs daily); optional row-count comparison with a live DB.
set -euo pipefail

BACKUP=${1:?backup file (.dump.age)}
IDENTITY=${2:?age identity (private key) file}
COMPARE=${3:-}
NAME=baixeai-restore-test-$$
NET=$NAME-net
PG_IMAGE=postgres:17.11-alpine
API_IMAGE=${API_IMAGE:-baixeai-api}
WORK=$(mktemp -d)
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: do not rewrite container paths (no effect on Linux)
absdir() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

echo "1/5 decrypting"
docker run --rm --user root --entrypoint age \
  -v "$(absdir "$(dirname "$BACKUP")")":/in:ro -v "$(absdir "$(dirname "$IDENTITY")")":/key:ro -v "$(absdir "$WORK")":/out \
  baixeai-backup -d -i "/key/$(basename "$IDENTITY")" -o /out/db.dump "/in/$(basename "$BACKUP")"
test -s "$WORK/db.dump"

echo "2/5 starting an empty PostgreSQL (isolated network)"
docker network create --internal "$NET" >/dev/null
docker run -d --name "$NAME" --network "$NET" -e POSTGRES_PASSWORD=restore -e POSTGRES_DB=restored "$PG_IMAGE" >/dev/null
for _ in $(seq 1 60); do docker exec "$NAME" pg_isready -U postgres -d restored >/dev/null 2>&1 && break; sleep 1; done

echo "3/5 restoring"
docker cp "$(absdir "$WORK")/db.dump" "$NAME":/tmp/db.dump
docker exec "$NAME" pg_restore --exit-on-error --no-owner --no-privileges -U postgres -d restored /tmp/db.dump

echo "4/5 integrity checks"
q() { docker exec "$NAME" psql -U postgres -d restored -tAc "$1"; }
tables=$(q "select count(*) from information_schema.tables where table_schema='public'")
trigger=$(q "select count(*) from pg_trigger where tgname in ('credit_ledger_append_only','audit_events_append_only')")
version=$(q "select version_num from alembic_version")
echo "   tables=$tables alembic=$version ledger_triggers=$trigger"
[ "$tables" -gt 10 ] && [ "$trigger" -eq 2 ]
docker run --rm --network "$NET" -e APP_ENV=development \
  -e DATABASE_URL="postgresql+psycopg://postgres:restore@$NAME:5432/restored" "$API_IMAGE" python -c "
from app.core.db import SessionLocal
from app.services.credits import ledger_mismatches
with SessionLocal() as db:
    bad = ledger_mismatches(db)
print('   ledger mismatches:', len(bad))
raise SystemExit(1 if bad else 0)"

echo "5/5 row counts"
restored=$(q "select string_agg(relname || '=' || (xpath('/row/c/text()', query_to_xml('select count(*) c from public.' || quote_ident(relname), false, true, '')))[1]::text, ' ' order by relname) from pg_stat_user_tables")
echo "   restored: $restored"
if [ -n "$COMPARE" ]; then
  live=$(eval "$COMPARE" "\"select string_agg(relname || '=' || (xpath('/row/c/text()', query_to_xml('select count(*) c from public.' || quote_ident(relname), false, true, '')))[1]::text, ' ' order by relname) from pg_stat_user_tables\"")
  echo "   live:     $live"
  [ "$restored" = "$live" ] || { echo "ROW COUNTS DIFFER (expected only if the live DB changed after the backup)"; exit 1; }
fi
echo "RESTORE TEST PASSED"
