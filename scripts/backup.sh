#!/usr/bin/env bash
# Encrypted logical backup of the database + media. Usage:
#   BACKUP_KEY_FILE=/secure/backup.key DATABASE_URL_PG=postgresql://... MEDIA_ROOT=/srv/var/media scripts/backup.sh /backups
# The key file must be stored separately from the backups (offline or in a secret manager).
set -euo pipefail
OUT=${1:?usage: backup.sh <output-dir>}
: "${BACKUP_KEY_FILE:?set BACKUP_KEY_FILE}" "${DATABASE_URL_PG:?set DATABASE_URL_PG (libpq URL)}"
TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$OUT"
umask 077
pg_dump --format=custom --no-owner --dbname="$DATABASE_URL_PG" \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$BACKUP_KEY_FILE" -out "$OUT/db-$TS.dump.enc"
if [ -n "${MEDIA_ROOT:-}" ] && [ -d "$MEDIA_ROOT" ]; then
  tar -C "$MEDIA_ROOT" -cf - . \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$BACKUP_KEY_FILE" -out "$OUT/media-$TS.tar.enc"
fi
( cd "$OUT" && sha256sum ./*"$TS"* > "manifest-$TS.sha256" )
echo "backup complete: $OUT (timestamp $TS)"
