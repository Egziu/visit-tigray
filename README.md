# VISIT TIGRAY

**Discover. Experience. Remember.**

A regional digital tourism platform for Tigray: an editorial discovery site in Tigrinya, Amharic and English; a cited, local-first
AI guide (the **Tigray Intelligence Engine**); a deterministic trip planner; the **Tigray Memories** community; governed
**Tourism Awards**; a verified provider directory; and a Bureau management console.

> **Status: pre-release engineering build.** This is not an official service of the Tigrai Culture and Tourism Bureau and must
> not be presented as one without written authorization. All bundled content is **synthetic or unverified development seed data**.
> See [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md) for open release blockers.
>
> Product owner: SERK Technologies Group · Intended institutional partner: Tigrai Culture and Tourism Bureau

## What's inside

| Area | Highlights |
|---|---|
| Backend (`backend/`) | FastAPI modular monolith · PostgreSQL 16 + PostGIS + pgvector · Alembic migrations · 159 API paths |
| Identity & security | Argon2id · server sessions + CSRF · TOTP MFA for all staff permissions · OIDC/Keycloak · data-driven roles · append-only hash-chained audit · least-privilege DB roles |
| CMS | Editor-defined categories · working copy + published snapshots · review/schedule/rollback · en/ti/am with human translation review · protected coordinates · advisories · Ethiopian calendar |
| Media | Upload validation, re-encoding, EXIF/GPS stripping, malware-scan hook, rights and "illustration/reconstruction" labels, duplicate detection |
| TIE (AI) | Knowledge Vault with governed ingestion · hybrid retrieval (vector + lexical + geo) · citations · six admin-controlled AI modes · egress guard proving fully-local operation · injection defences · evaluation suite |
| Planner | Deterministic, advisory-aware, accessibility-honest itineraries · versions · share links · ICS/PDF |
| Community | Pre-moderated stories with consent · comments, follows, blocks, reports, appeals · data export and deletion |
| Ecosystem | Provider verification and inquiries (bookings designed but disabled) · competitions with four-eyes governance · privacy-conscious analytics with provenance · read-only Bureau assistant |
| Frontend (`web/`) | Next.js public site + Bureau console + PWA (see [`docs/FRONTEND.md`](docs/FRONTEND.md)) |
| Ops | Docker Compose profiles · CI (lint, types, security scans, migrations, tests, eval, SBOM) · encrypted backups with restore rehearsal · Prometheus/Grafana |

## Quick start

```bash
cp .env.example .env            # set every secret
docker compose up -d --build    # db, redis, migrate, api, worker, web
```

Without Docker, and for the dev seed with an admin account, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

```bash
cd backend && .venv/bin/pytest          # 107 tests against a throwaway PostgreSQL database
.venv/bin/python -m app.modules.tie.evaluation --mode retrieval_only
```

## Documentation

* Vision & research: [Product vision](docs/PRODUCT_VISION.md) · [Global benchmark](docs/research/GLOBAL_BENCHMARK.md) · [Baseline audit](docs/BASELINE_AUDIT.md) · [Backlog](docs/BACKLOG.md) · [Roadmap](docs/ROADMAP.md)
* Architecture: [System](docs/SYSTEM_ARCHITECTURE.md) · [Database](docs/DATABASE_DESIGN.md) · [Local AI](docs/LOCAL_AI_ARCHITECTURE.md) · [Offline](docs/OFFLINE_ARCHITECTURE.md) · [ADRs](docs/adr/) · [OpenAPI](docs/api/openapi.json)
* Governance: [Knowledge governance](docs/KNOWLEDGE_GOVERNANCE.md) · [AI model evaluation](docs/AI_MODEL_EVALUATION.md) · [Threat model](docs/THREAT_MODEL.md) · [Privacy](docs/PRIVACY_AND_DATA_GOVERNANCE.md) · [Security policy](SECURITY.md)
* Operations: [Deployment](docs/DEPLOYMENT.md) · [Backup & recovery](docs/BACKUP_AND_RECOVERY.md) · [Bureau user guide](docs/BUREAU_USER_GUIDE.md)
* Quality: [Test plan](docs/TEST_PLAN.md) · [Test report](docs/TEST_REPORT.md) · [Release readiness](docs/RELEASE_READINESS.md) · [Changelog](CHANGELOG.md)
* Contributors and AI agents: read [`CLAUDE.md`](CLAUDE.md) first.

## Principles

Never fabricate facts, prices, hours, permits or travel conditions · unknown stays unknown · AI explains, people decide · sacred
and restricted heritage stays protected · every claim is sourced · build for low connectivity.

The original v0.1 prototype is preserved in [`legacy/prototype-v0.1`](legacy/prototype-v0.1).

© 2026 SERK Technologies Group.
