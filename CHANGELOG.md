# Changelog

All notable changes are listed here. The project follows semantic versioning from 2.0.0 onward.

## [Unreleased] — 2.0.0-dev

### Added
- Visit Tigray logo across the site, PWA icons, favicon and social-share image.
- Journals (Substack-like publications, subscriptions and email digests) and Spaces (Discord-like channels with live SSE
  updates, replies, reactions, slow mode, held messages); in-app notifications.
- Guide action chips (open planner / destination), conversation history and starter prompts; planner summary, pre-travel
  checklist, per-stop alternatives and server-validated drag-and-drop editing.
- Modular FastAPI backend on PostgreSQL 16 + PostGIS + pgvector, with Alembic migrations 0001–0004.
- Identity: Argon2id passwords, server-side sessions, CSRF, lockout, email verification, password reset, TOTP MFA for staff,
  OIDC (authorization code + PKCE), configurable roles and permissions.
- Append-only, hash-chained audit log with verification endpoint.
- Destination CMS with categories, translations (machine/draft/reviewed), revisions, diff, rollback, scheduling, archive,
  aliases and cross-script search; advisories, events with Ethiopian dates, verified route segments.
- Controlled media pipeline replacing external image URLs.
- Knowledge Vault and Tigray Intelligence Engine: governed ingestion, hybrid retrieval, citations, AI modes, egress guard,
  policy engine, tool gateway, personas, model registry, evaluation framework and a 34-item en/ti/am dataset.
- Deterministic planner with saved itineraries, share links, ICS and PDF export.
- Tigray Memories community, provider directory, governed awards, privacy-conscious analytics, Bureau assistant, worker.
- Docker Compose stack, least-privilege database roles, encrypted backups and restore rehearsal, CI pipeline, SBOM, load-test baseline.
- Next.js frontend with public site, Bureau console and PWA (see `docs/FRONTEND.md`).
- Documentation set (architecture, governance, threat model, privacy, deployment, recovery, user guide, ADRs).

### Changed
- Prototype moved to `legacy/prototype-v0.1`; its six destinations and editorial copy are preserved in the development seed.
- Shared admin token replaced by real identity and permissions.

### Security
- Pillow upgraded to 13.0.0 (pip-audit reported 40 known vulnerabilities in 12.3.0).
- Fixed: live destinations disappeared from public view while a draft edit was pending.

## [0.1.0] — prototype
- Single-file FastAPI + SQLite prototype with static page, curated planner, moderated memories and token-gated admin.
