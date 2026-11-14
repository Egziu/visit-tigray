#!/usr/bin/env bash
# Pre-deploy (Railway/compose): migrate as the schema owner, re-apply runtime grants, optional staging seed + admin bootstrap.
set -euo pipefail
cd /srv/backend
DATABASE_URL="${DATABASE_MIGRATION_URL:-$DATABASE_URL}" alembic upgrade head
if [ -n "${DATABASE_MIGRATION_URL:-}" ]; then
  psql "${DATABASE_MIGRATION_URL/+psycopg/}" -v ON_ERROR_STOP=1 -q -f /srv/infra/postgres/post-migrate-grants.sql
fi
if [ "${SEED_STAGING:-false}" = "true" ]; then
  python -m app.seed --allow-staging
fi
python -m app.bootstrap_admin
