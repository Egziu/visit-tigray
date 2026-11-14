#!/usr/bin/env bash
# Restore an encrypted backup into an EMPTY target database. Usage:
#   BACKUP_KEY_FILE=... TARGET_URL_PG=postgresql://.../visit_tigray_restore scripts/restore.sh /backups/db-<TS>.dump.enc [media-<TS>.tar.enc MEDIA_ROOT]
set -euo pipefail
DUMP=${1:?usage: restore.sh <db-dump.enc> [media.tar.enc media-root]}
: "${BACKUP_KEY_FILE:?}" "${TARGET_URL_PG:?}"
dir=$(dirname "$DUMP"); ts=$(basename "$DUMP" | sed -E 's/^db-(.*)\.dump\.enc$/\1/')
if [ -f "$dir/manifest-$ts.sha256" ]; then ( cd "$dir" && sha256sum --check --quiet "manifest-$ts.sha256" ); fi
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$BACKUP_KEY_FILE" -in "$DUMP" \
  | pg_restore --no-owner --exit-on-error --dbname="$TARGET_URL_PG"
if [ -n "${2:-}" ]; then
  mkdir -p "${3:?media root required}"
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$BACKUP_KEY_FILE" -in "$2" | tar -C "$3" -xf -
fi
echo "restore complete into $TARGET_URL_PG"
