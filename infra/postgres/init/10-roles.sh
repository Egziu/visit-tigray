#!/bin/sh
# Least-privilege roles (docs/THREAT_MODEL.md §Database):
#   vt_migrator — owns the schema, runs Alembic (DATABASE_MIGRATION_URL)
#   vt_app      — runtime role: DML only; may INSERT but never UPDATE/DELETE/TRUNCATE the audit log
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vt_migrator') THEN
    CREATE ROLE vt_migrator LOGIN PASSWORD '${VT_MIGRATOR_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vt_app') THEN
    CREATE ROLE vt_app LOGIN PASSWORD '${VT_APP_PASSWORD}';
  END IF;
END \$\$;
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO vt_migrator, vt_app;
GRANT USAGE, CREATE ON SCHEMA public TO vt_migrator;
GRANT USAGE ON SCHEMA public TO vt_app;
ALTER DEFAULT PRIVILEGES FOR ROLE vt_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vt_app;
ALTER DEFAULT PRIVILEGES FOR ROLE vt_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO vt_app;
SQL
