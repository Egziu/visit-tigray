# Test Report

Date: 2026-11-12 · Branch `claude/cool-curie-tnderx` · Every result below comes from a command actually run in this session.
Authoring host: 4 vCPU Intel Xeon @ 2.1 GHz, 15 GB RAM, PostgreSQL 16.x + PostGIS 3.4.2 + pgvector 0.6.0, Python 3.12, Node 22.

## 1. Baseline (prototype v0.1)
`pytest -q` → **5 passed** (Python 3.13). See `docs/BASELINE_AUDIT.md`.

## 2. Backend

| Check | Command | Result |
|---|---|---|
| Unit + integration + API tests | `cd backend && .venv/bin/pytest` | **107 passed** (incl. 9 Journals/Spaces tests; real PostgreSQL, real PostgreSQL; a fresh database is migrated by Alembic per run) |
| Line coverage | `pytest --cov=app` | **90%** (5,756 statements; measured at 96 tests) |
| Lint | `ruff check .` | clean |
| Types | `mypy app` | no issues (78 files) |
| Security lint | `bandit -c pyproject.toml -r app` | 0 issues |
| Dependency audit | `pip-audit -r requirements.lock` / dev lock | no known vulnerabilities (after Pillow 12.3.0 → 13.0.0, which fixed 40 advisories) |
| Migrations | `alembic upgrade head` → `downgrade base` → `upgrade head` → `alembic check` | pass; "No new upgrade operations detected" |
| SBOM | `cyclonedx-py requirements requirements.lock` | `docs/sbom-backend.cdx.json` |

Coverage by required test type:

| Required test | Where | Status |
|---|---|---|
| Unit | `test_core_units.py` (calendar incl. 8,572-date round trip, Ethiopic text, egress policy) | ✅ |
| Integration / API contract | all suites via FastAPI TestClient against PostgreSQL; OpenAPI exported | ✅ (no schemathesis-style fuzzing yet) |
| Database migration | CI job + local round trip | ✅ |
| Authorization | `test_authz_matrix.py` (every `/api/bureau` + `/api/judging` route: 401 anon, 403 visitor, 403 MFA-pending) + per-feature denied cases | ✅ |
| Security regression | CSRF, lockout, password policy, headers, trusted hosts, body limit, rate limit, OIDC token validation (alg confusion, nonce, audience, issuer, expiry, PKCE), audit tamper detection | ✅ |
| Upload validation | `test_media.py` (EXIF/GPS stripped, polyglots, non-images, rights, signed URLs, dedupe) | ✅ |
| Moderation workflow | `test_community.py` (pre-moderation, AI flags advisory, self-moderation blocked, reports, independent appeals) | ✅ |
| Competition workflow | `test_ecosystem.py` (gates, four-eyes, COI, anonymity, rubric validation, integrity flags, winner approval, certificates) | ✅ |
| Geographic planning | `test_planner.py` (verified vs straight-line, advisories, accessibility, pace caps, manual edits, ICS/PDF, share revocation) | ✅ |
| Multilingual | calendar, folding/transliteration, cross-script search, ti/am refusals, translation workflow | ✅ |
| AI retrieval evaluation | `evaluation.py` run (below) | ✅ |
| AI citation validation | invalid citation removed, uncited answers downgraded, unsupported operational claims flagged | ✅ |
| Prompt-injection resistance | direct (en/ti/am), indirect (document screening + neutralization), tool-call manipulation | ✅ |
| AI privacy / permission | restricted canary never returned to public or internal-only staff; conversations private; **socket-level egress test** | ✅ |
| Backup & recovery | restore rehearsal (§4) | ✅ (dev-sized) |
| Load | Locust (§5) | ✅ (baseline only) |
| End-to-end browser, mobile, accessibility, offline sync | frontend (§3) | ✅ automated; manual audits pending |

### AI evaluation (retrieval-only, hashing embeddings, no LLM)
`python -m app.modules.tie.evaluation --mode retrieval_only` → **31/34 passed (91%)**. Safety categories (circumvention, restricted,
prompt injection, unanswerable, unanswerable-operational, outdated travel) **100%**. Failures: 2 cross-lingual misses (ti/am questions
whose evidence is English-only) and **1 wrong-document citation (am-fest-01)**. Report: `docs/ai-eval/2026-11-12-retrieval-only.md`.
LLM generation quality is **not measured** (no weights or GPU reachable).

## 3. Frontend (from `docs/FRONTEND.md`, run against the real backend)

| Check | Result |
|---|---|
| `npm run lint` / `typecheck` / `build` | pass |
| Vitest | **36 passed** |
| Playwright e2e (headless Chromium) | **45 passed**: locales, destinations, cross-lingual search, live guide with citations, planner, Bureau sign-in gate, offline cache, mobile 390×844 without horizontal scroll, Journals and Spaces signed out, and **signed in with two synthetic users**: live chat delivery and reactions over SSE without reload, Journal submission entering human review, saving an itinerary |
| axe-core (WCAG 2.0/2.1/2.2 A+AA) | **0 serious/critical** violations on 10 pages |

Five frontend defects were found by these tests and fixed (contrast 1.11:1, every destination page 404ing, missing `lang` on 404,
guide crash after answering, nested-interactive map).

The signed-in chat test then found a sixth: **Server-Sent Events were buffered** when proxied through the Next.js server, because it
gzip-compressed `text/event-stream` responses, so messages only appeared after polling. Fixed by sending
`Cache-Control: no-store, no-transform` and `X-Accel-Buffering: no`, emitting an immediate `ready` event, and only showing "Live" in
the UI after that event arrives (otherwise a 6 s watchdog falls back to polling and says so).

## 4. Operations rehearsals

* **Least privilege** (fresh database, production role scripts): runtime role `vt_app` could read and append audit rows, and got
  *permission denied* for `UPDATE`/`DELETE`/`TRUNCATE audit_events`, `ALTER TABLE` and `CREATE TABLE`.
* **Backup/restore:** encrypted dump and restore with matching row counts, embeddings and geometries; 0.22 s backup / 0.87 s restore
  on development-sized data (not predictive of production).
* **Compose:** `docker compose config` valid for all profiles. Images were **not** built locally (no Docker daemon); CI builds them.

## 5. Load baseline
Locust, 50 users, 60 s, single source IP, 2 uvicorn workers, seeded dev DB: p95 **45 ms** `/api/destinations`, **42 ms** destination
detail, **24 ms** search, **17 ms** events, **70 ms** planner; 0 errors on these routes. `/api/tie/ask` returned 429 for 82% of calls,
because the per-IP AI rate limit (20/min) worked as designed with all virtual users on one IP. Raw CSV: `docs/loadtest-2026-11-12-stats.csv`.

## 6. Not executed / open
* Real local-LLM quality and latency benchmarks (blocked: no weights or GPU).
* Live ClamAV, SMTP, Keycloak and S3 integrations (protocol-level tests or mocks only).
* Manual screen-reader audits (en/ti/am), real-device mobile testing, native-speaker review.
* Signed-in browser e2e for memories and Bureau editing (covered by API tests; Spaces, Journals and itineraries now have browser tests).
* Independent penetration test.
* Point-in-time recovery rehearsal; production-sized restore timing.

## 13 November 2026 revalidation

See [current validation and remaining release gates](VALIDATION_2026-11-13.md).
These fresh observations supersede earlier readiness claims only for checks explicitly rerun.
