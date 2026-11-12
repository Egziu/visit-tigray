# Backup and Recovery

## 1. What is backed up

| Asset | Method | Encryption |
|---|---|---|
| PostgreSQL (all data, including embeddings and geometries) | `pg_dump --format=custom` via `scripts/backup.sh` | AES-256-CBC, PBKDF2 (200k iterations), key file kept separately |
| Media variants | `tar` of `MEDIA_ROOT` via `scripts/backup.sh` | same |
| Integrity | `manifest-<ts>.sha256`, checked by `scripts/restore.sh` | — |
| Knowledge index | rebuildable from documents: `POST /api/bureau/knowledge/reindex` | — |
| Model weights | not backed up here; re-pull from the authorized model store | — |

**Point-in-time recovery (PITR):** for production, enable WAL archiving (`archive_mode=on`, `archive_command` to encrypted object
storage, e.g. with pgBackRest or WAL-G), plus a weekly base backup. This is **configuration-dependent and not rehearsed in this
branch** (unresolved). Logical dumps are the tested baseline.

## 2. Schedule (proposed)

* Logical dump: every 6 hours, retained 35 days; plus weekly copies retained 12 months.
* At least one copy off-site, in an approved location (data residency), with keys held by two named officers.

## 3. Recovery objectives

| Objective | Target (proposed) | Evidence |
|---|---|---|
| RPO (data loss) | ≤ 6 h with dumps; ≤ 5 min with PITR | PITR not yet rehearsed |
| RTO (time to restore service) | ≤ 4 h | Rehearsal below measured **0.22 s backup / 0.87 s restore on a development-sized database** (6 destinations, 9 documents). **This does not predict production RTO.** Rehearse again on production-sized data |

## 4. Restore procedure

```bash
# 1. Create an empty database with extensions (as superuser)
psql -c "CREATE DATABASE visit_tigray_restore"
psql -d visit_tigray_restore -c "CREATE EXTENSION postgis; CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;"
# 2. Decrypt, verify the manifest and restore
BACKUP_KEY_FILE=/secure/backup.key TARGET_URL_PG=postgresql:///visit_tigray_restore \
  scripts/restore.sh /backups/db-<TS>.dump.enc /backups/media-<TS>.tar.enc /srv/var/media
# 3. Re-apply grants for the runtime role, then point DATABASE_URL at the restored DB
psql -d visit_tigray_restore -f infra/postgres/post-migrate-grants.sql
# 4. Verify: health endpoint, audit chain, row counts, a sample of published pages, retrieval
curl -s localhost:8000/api/health
```

## 5. Rehearsal (performed 2026-11-12)

`SOURCE_DB=vt_priv scripts/restore-rehearsal.sh` backed up a seeded database created through the production role setup, restored it
into a fresh database and compared:

```
  ok   users: 0 rows
  ok   destinations: 6 rows
  ok   destination_revisions: 6 rows
  ok   knowledge_documents: 9 rows
  ok   knowledge_chunks: 10 rows
  ok   audit_events: 1 rows
  ok   memories: 0 rows
  ok   itineraries: 0 rows
  ok   SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL
  ok   SELECT count(*) FROM destinations WHERE location IS NOT NULL
backup: 0.22s  restore: 0.87s  encrypted size: 184K
```

Run the rehearsal **quarterly** and after any schema change, and record results here.
