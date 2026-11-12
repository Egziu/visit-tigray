-- Run as vt_migrator after every `alembic upgrade head` (scripts/migrate.sh does this).
-- The audit log is append-only for the runtime role even if the trigger were disabled.
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM vt_app;
GRANT SELECT, INSERT ON audit_events TO vt_app;
REVOKE ALL ON alembic_version FROM vt_app;
GRANT SELECT ON alembic_version TO vt_app;
