# Deployment

> The platform is **pre-release** and **not an official government service**. Deploy only to private staging environments until
> the Bureau gives written authorization and the release blockers in `docs/RELEASE_READINESS.md` are closed.

## 1. Local development (no Docker)

Prerequisites: Python 3.12+, Node 22, PostgreSQL 16 with PostGIS 3.4 and pgvector, and `uv`.

```bash
# database (Ubuntu): sudo apt-get install postgresql-16-postgis-3 postgresql-16-pgvector
createdb visit_tigray
cd backend
uv venv .venv && uv pip install -p .venv -r requirements.lock -r requirements-dev.lock
export DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/visit_tigray ENVIRONMENT=development
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed --dev-admin you@example.org     # synthetic seed; prints a one-time password
.venv/bin/uvicorn app.main:app --reload                      # API on :8000, docs at /api/docs
.venv/bin/python -m app.worker                               # separate terminal
cd ../web && npm ci && API_ORIGIN=http://localhost:8000 npm run dev   # site on :3000
```

The dev admin must enrol TOTP MFA at first sign-in (any authenticator app) before staff permissions activate.

Tests: `cd backend && .venv/bin/pytest` (creates and drops its own database; set `TEST_DATABASE_ADMIN_URL` if your server needs a
password).

## 2. Docker Compose (development / initial deployments)

```bash
cp .env.example .env        # fill EVERY secret; never commit .env
docker compose up -d --build                         # db, redis, migrate, api, worker, web
docker compose --profile ai up -d ollama             # local inference
docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M   # example; evaluate first
docker compose --profile scan up -d clamav           # then set CLAMD_HOST=clamav
docker compose --profile observability up -d         # Prometheus :9090, Grafana :3001
```

The `migrate` service runs `alembic upgrade head` as `vt_migrator`, then applies `infra/postgres/post-migrate-grants.sql`. The API
and worker run as the restricted `vt_app` role.

**Verification status:** `docker compose config` was validated for all profiles in the build environment. Images were **not** built
or started there (no Docker daemon). CI builds the images (`compose` job).

## 3. Production checklist

* `ENVIRONMENT=production`. Startup refuses weak `SECRET_KEY`, disabled staff MFA, or a missing malware scanner.
* TLS-terminating reverse proxy (nginx, Caddy or Traefik) in front of `web:3000` and `api:8000`, routing `/api/*` and `/metrics`
  (internal only) to the API. Set `FORWARDED_ALLOW_IPS` to the proxy address and `ALLOWED_HOSTS`/`CORS_ORIGINS` to real hostnames.
* `REDIS_URL` set, so rate limits are shared across workers.
* `CLAMD_HOST` set, plus media on encrypted storage (S3/MinIO with SSE — the S3 backend is a documented extension point, not yet
  implemented).
* OIDC via Keycloak, with an MFA policy enforced at the IdP (`amr` must include `otp`/`mfa`).
* Backups scheduled with off-site copies; restore rehearsal recorded (see `docs/BACKUP_AND_RECOVERY.md`).
* Prometheus alerts on 5xx rate, p95 latency, failed or dead jobs, and audit-chain verification.
* AI mode `fully_local` or `retrieval_only` unless the Bureau has approved a cloud mode in writing.
* Feature flags `bookings`, `payments`, `public_voting` and `competitions_live` remain **off** until approvals exist.

## 4. Edge / offline deployment (institutional server)

For sites with unreliable uplinks, deploy the same Compose stack on a local server with `AI_DEFAULT_MODE=offline` or `fully_local`,
seeded from a backup of the central database. Visitors on the local network use it directly; the PWA caches content for full
disconnection. Synchronization between edge and central is **not implemented** (planned; see `docs/OFFLINE_ARCHITECTURE.md`).
