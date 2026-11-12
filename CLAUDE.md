# CLAUDE.md — Engineering instructions for Visit Tigray

Permanent instructions for human developers and AI coding agents working in this repository.
Read this before changing anything.

## What this is
Visit Tigray is a regional digital tourism platform: public discovery site, Tigray Intelligence
Engine (TIE, local-first AI), Knowledge Vault, deterministic itinerary planner, Tigray Memories
community, Tourism Awards, verified provider directory and the Bureau console.
Product owner: SERK Technologies Group. Intended institutional partner: Tigrai Culture and Tourism
Bureau. **It is not an official government service until the Bureau authorizes it in writing.**

## Layout
```
backend/              FastAPI modular monolith (Python 3.12+)
  app/core/           config, db, security, rate limiting, egress guard, i18n/Ethiopic, calendar
  app/modules/<mod>/  models.py · schemas.py · service.py · router.py per bounded context
  migrations/         Alembic (the ONLY way schema changes)
  tests/              pytest (needs PostgreSQL with PostGIS + pgvector)
web/                  Next.js (App Router, TypeScript, Tailwind) public site + /bureau console
evals/                TIE evaluation datasets
infra/                Docker images (postgres), observability config
scripts/              backup/restore, dev helpers
docs/                 architecture, governance, ADRs (docs/adr/)
legacy/prototype-v0.1 original prototype, kept for reference only (not run)
```

## Commands
```bash
# backend
cd backend && uv venv && uv pip install -r requirements.lock
export DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/visit_tigray
alembic upgrade head && python -m app.seed      # seed = clearly labelled synthetic dev data
uvicorn app.main:app --reload
pytest -q                                        # uses TEST_DATABASE_URL (created/dropped per run)
ruff check . && mypy app
# frontend
cd web && npm ci && npm run dev | npm run build | npm run lint | npm test | npm run e2e
```

## Non-negotiable rules
1. **Never fabricate** hotels, prices, opening hours, contacts, permits, road conditions, safety
   conditions or historical claims — in code, seed data, prompts or tests. Unknown stays `null`/
   "unknown" and the UI says so. Seed data is labelled `synthetic` / `unverified`.
2. **AI never decides feasibility or publishes.** The planner is deterministic; TIE only explains.
   The AI never gets raw DB, shell or admin access; tools are allowlisted and typed, and they run
   with the *caller's* permissions (`app/modules/tie/tools.py`).
3. **Retrieved documents and user content are data, not instructions.** Keep them inside the data
   delimiters built by `tie/context.py`. Permission filtering happens in SQL, before the model
   sees anything.
4. **Fully-local mode means zero external egress** for conversations, documents, embeddings and
   analytics. All outbound HTTP must go through `app/core/egress.py`. Never use `urllib`/raw
   `httpx` directly for external calls.
5. **Sensitive heritage**: restricted/sacred knowledge and precise coordinates of flagged sites are
   only returned to users with the matching permission. Public responses use coarsened coordinates.
6. **Authorization lives in the server**, via `require(perm)` dependencies plus object-level checks
   in services. Every new route needs an authorization test, including the denied case.
7. **Every privileged state change writes an audit event** (`audit.record(...)`). The audit table is
   append-only (DB trigger) and hash-chained.
8. Feature flags (`bookings`, `payments`, `public_voting`, `competitions_live`) stay **off** until
   institutional, legal and security approvals exist.
9. Machine translations are stored with `status=machine` and never shown as reviewed.
10. No secrets, real personal data, private Bureau records or model weights in git.
11. Media: only through `media` module uploads (validated, re-encoded, EXIF-stripped, quarantined).
    No arbitrary external image URLs.
12. Don't claim tests, scans, benchmarks or compliance you didn't run. Update `docs/TEST_REPORT.md`
    with real output.

## Conventions
- Python: typed, `ruff` clean, SQLAlchemy 2.0 style, Pydantic v2 schemas for every request/response.
  Errors are `{"error": {"code", "message", "details"}}` via `app/core/errors.py`.
- Migrations: `alembic revision --autogenerate -m "..."`, then review by hand. Extensions, triggers
  and grants go in explicit `op.execute`.
- Frontend: server components by default. All UI strings live in `web/messages/{en,ti,am}.json`.
  Use the design tokens in `web/app/globals.css`, never ad-hoc colours. Respect `prefers-reduced-motion`.
- Commits: small, meaningful, imperative subject. Never force-push; never merge to `main` unreviewed.
- Record significant decisions as ADRs in `docs/adr/NNNN-title.md`.

## Definition of done
Works end-to-end in the real app · authorization enforced · error/loading states · accessible ·
critical paths tested (including failure cases) · docs updated · security reviewed · limitations
disclosed · reproducible from documented commands.
