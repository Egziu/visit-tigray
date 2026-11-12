# Implementation Backlog

Priority: **P0** = release blocker for any pilot · **P1** = pilot scope · **P2** = post-pilot.
Status values: `done` (implemented + tested in this branch), `partial`, `todo`, `blocked` (needs external input).
The status column is updated as work lands; `docs/TEST_REPORT.md` holds the evidence.

| ID | Item | Pri | Acceptance criteria | Status |
|---|---|---|---|---|
| B-01 | Modular backend with Alembic migrations on PostgreSQL + PostGIS + pgvector | P0 | `alembic upgrade head` works on an empty DB; downgrade/upgrade round-trip test passes; no schema created at import time | |
| B-02 | Identity: accounts, Argon2id, sessions, CSRF, email verification, password reset | P0 | Login/logout/reset flows tested, including failure cases; session cookie is HttpOnly+SameSite; unsafe cookie-auth requests without CSRF get 403 | |
| B-03 | Staff MFA (TOTP) required for staff permissions | P0 | A staff permission without verified MFA gets 403 in tests | |
| B-04 | OIDC (Keycloak-compatible) login with PKCE | P0 | ID-token signature/issuer/audience/nonce validation unit-tested against a local JWKS | |
| B-05 | Configurable roles and permissions, plus object-level checks | P0 | An authorization matrix test covers every staff route | |
| B-06 | Tamper-evident append-only audit log | P0 | DB trigger rejects UPDATE/DELETE; hash-chain verification detects tampering | |
| B-07 | Security headers, CSP, rate limiting, request-size limits, trusted hosts | P0 | Header and 429 tests | |
| B-08 | Destination CMS: categories (editor-created), translations, revisions, rollback, workflow, scheduled publish, sources, verification dates | P0 | An editor creates a category with no code change; publish needs the publish permission; rollback restores the prior revision | |
| B-09 | Travel advisories that gate planning | P0 | A "travel not advised" advisory disables routing and offers virtual exploration | |
| B-10 | Controlled media pipeline: magic-byte validation, re-encoding, EXIF strip, quarantine, scan hook, signed URLs | P0 | Test proves GPS EXIF is removed; polyglot/oversized files rejected | |
| B-11 | Knowledge Vault workflow (upload → scan → extract → language → review → approve → chunk → embed → index → publish) | P0 | Restricted docs never retrieved for unauthorized callers (test) | |
| B-12 | Hybrid retrieval (vector + lexical + geo + metadata + rerank, cross-lingual aliases) | P1 | Retrieval eval reports hit@k | |
| B-13 | TIE provider abstraction (Ollama, llama.cpp, vLLM/OpenAI-compatible, retrieval-only) and AI operating modes | P0 | In fully-local mode an external provider call is blocked before any socket opens (egress test) | |
| B-14 | Citation validation, injection defence, policy engine, allowlisted tool gateway | P0 | Injection, restricted-knowledge and uncited-output tests pass | |
| B-15 | AI evaluation framework with en/ti/am cases | P1 | `python -m app.modules.tie.evaluation` produces a report; ti/am items flagged for native-speaker review | |
| B-16 | Deterministic planner (clustering, time budgets, accessibility, permits, verified vs estimated distances, explanations, versions, share links, ICS/PDF/print) | P0 | Unknown access stays unknown; no AI controls feasibility | |
| B-17 | Multilingual: externalized UI strings en/ti/am, Ethiopic normalization, aliases, transliteration, Ethiopian calendar, translation workflow, missing-translation report | P0 | Calendar conversion tests vs known dates; machine translations never shown as reviewed | |
| B-18 | Community / Tigray Memories: profiles, journals, albums, media, comments, follows, saves, reports, blocks, appeals, export/delete | P1 | Pending content invisible; blocked users can't comment; export contains only own data | |
| B-19 | Awards: competitions, gates, rubrics, anonymous judging, COI, duplicate detection, four-eyes winner approval, sponsors, fulfilment, appeals, certificates | P1 | A competition can't open without legal + funding + Bureau authorization; the same person can't both propose and approve winners | |
| B-20 | Provider marketplace with verification, inquiries, booking architecture behind disabled feature flag | P1 | Booking endpoints return 403 while the flag is off | |
| B-21 | Notifications outbox + DB job queue with idempotency | P1 | Duplicate idempotency key creates no duplicate job | |
| B-22 | Privacy-conscious analytics with CSV/XLSX/PDF exports and provenance | P1 | Analytics never store user id or IP; exports carry filters + timestamp | |
| B-23 | Bureau AI assistant scoped to caller permissions, drafts only | P1 | Assistant can't publish (test) | |
| B-24 | Next.js public site + Bureau console with design system, light/dark, reduced motion | P0 | `next build` passes; Playwright smoke + axe checks pass | |
| B-25 | PWA: offline pages, content packs, offline itinerary, sync queue | P1 | Playwright offline test loads a cached destination | |
| B-26 | Observability: structured logs, Prometheus metrics, OTel hook | P1 | `/metrics` exposes request and AI latency histograms | |
| B-27 | Backups: encrypted pg_dump, restore rehearsal, index rebuild | P0 | Rehearsal executed with measured duration | |
| B-28 | CI: lint, type check, tests, pip-audit, npm audit, SBOM, build | P0 | Workflow committed | |
| B-29 | Docker Compose environment (db with PostGIS+pgvector, redis, minio, keycloak, ollama, api, web, worker) | P1 | Compose file validated (`docker compose config`) where Docker is available | |
| B-30 | Real local-model benchmarks (latency, ti/am quality) | P1 | Measured on target hardware | blocked: no model weights/GPU reachable from build environment |
| B-31 | Licensed photography and Bureau-approved content | P0 | Rights register filled | blocked: institutional input |
| B-32 | Native-speaker review of Tigrinya/Amharic UI strings, glossary, eval set | P0 | Reviewer sign-off recorded | blocked: qualified reviewers |
| B-33 | Legal review (privacy, competitions, tourism, heritage) | P0 | Written opinion | blocked: counsel |
| B-34 | Immersive heritage: virtual exhibitions, timelines, 360°/3D viewers | P2 | Viewer loads approved, labelled media | |
| B-35 | Voice (STT/TTS), image interpretation, OCR | P2 | Interfaces + measured quality | |
