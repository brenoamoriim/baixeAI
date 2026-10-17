#!/bin/sh
# citext is required by the schema (case-insensitive e-mails) in both databases.
set -e
for db in "$POSTGRES_DB" baixeai_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" -c "CREATE EXTENSION IF NOT EXISTS citext;"
done
