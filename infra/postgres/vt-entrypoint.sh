#!/usr/bin/env bash
# Refuse to INITIALISE a new cluster unless every password is present. A partial first start would
# run initdb, fail in the role script, and leave a cluster the image never re-initialises.
set -euo pipefail
PGDATA="${PGDATA:-/var/lib/postgresql/data}"
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  missing=""
  for v in POSTGRES_PASSWORD VT_APP_PASSWORD VT_MIGRATOR_PASSWORD; do
    [ -n "${!v:-}" ] || missing="$missing $v"
  done
  if [ -n "$missing" ]; then
    echo "vt-entrypoint: refusing to initialise database; missing:$missing (set them, then redeploy)" >&2
    exit 1
  fi
fi
exec docker-entrypoint.sh "$@"
