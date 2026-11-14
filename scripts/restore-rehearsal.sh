#!/usr/bin/env bash
# Restore rehearsal: back up SOURCE, restore into a fresh database, verify integrity, report timings.
# Usage: SOURCE_DB=vt_priv PGHOST=localhost PGUSER=postgres scripts/restore-rehearsal.sh
set -euo pipefail
SRC=${SOURCE_DB:?}; DST="${SRC}_restore_check"
work=$(mktemp -d); key="$work/key"; head -c 48 /dev/urandom | base64 > "$key"
here=$(cd "$(dirname "$0")" && pwd)
t0=$(date +%s.%N)
BACKUP_KEY_FILE=$key DATABASE_URL_PG="postgresql:///$SRC" "$here/backup.sh" "$work/out" >/dev/null
t1=$(date +%s.%N)
psql -q -d postgres -c "DROP DATABASE IF EXISTS $DST WITH (FORCE)" -c "CREATE DATABASE $DST"
psql -q -d "$DST" -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
dump=$(ls "$work"/out/db-*.dump.enc)
BACKUP_KEY_FILE=$key TARGET_URL_PG="postgresql:///$DST" "$here/restore.sh" "$dump" >/dev/null 2>"$work/restore.err" || { grep -v "already exists" "$work/restore.err" >&2 || true; }
t2=$(date +%s.%N)
fail=0
for t in users destinations destination_revisions knowledge_documents knowledge_chunks audit_events memories itineraries; do
  a=$(psql -tAq -d "$SRC" -c "SELECT count(*) FROM $t"); b=$(psql -tAq -d "$DST" -c "SELECT count(*) FROM $t")
  [ "$a" = "$b" ] && echo "  ok   $t: $a rows" || { echo "  FAIL $t: source=$a restored=$b"; fail=1; }
done
# embeddings & geography survived (non-null counts)
for q in "SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL" "SELECT count(*) FROM destinations WHERE location IS NOT NULL"; do
  [ "$(psql -tAq -d "$SRC" -c "$q")" = "$(psql -tAq -d "$DST" -c "$q")" ] && echo "  ok   $q" || { echo "  FAIL $q"; fail=1; }
done
size=$(du -sh "$work/out" | cut -f1)
printf "backup: %.2fs  restore: %.2fs  encrypted size: %s\n" "$(echo "$t1-$t0" | bc)" "$(echo "$t2-$t1" | bc)" "$size"
rm -rf -- "$work"
psql -q -d postgres -c "DROP DATABASE $DST WITH (FORCE)"
exit $fail
