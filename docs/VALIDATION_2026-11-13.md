# Engineering validation — 13 November 2026

**Not production ready. This increment does not complete the requested product scope.**

## History and scope

`main` at `6fed7cb71aa62fe7bb84b2de4b9f370751bb9f87` contains README and the v0.1 ZIP.
Read-only remote discovery found `claude/cool-curie-tnderx` at
`313443f5c5a9808b7586d98b9a916b0a2921386c`, with the expanded FastAPI/PostgreSQL and Next.js application.
`feature/production-slices-validation` starts from that commit. No v0.2 archive was supplied or found;
no archive was extracted over existing source. The legacy prototype and manuscript-inspired frontend are preserved.
The intended institution is the Tigray Culture and Tourism Bureau, as clarified by the requester.
This identifies the institution, not an OIDC issuer or government-branding authorization.

## Changes in this increment

- Held or blocked messages cannot leak through another message's reply preview.
- Live streams revalidate sessions, moderation permissions and blocks each poll. Hidden updates become redacted
  tombstones; batches over 100 no longer advance the cursor past unprocessed updates.
- Compose uses the fail-closed predeployment script. Migration/grant errors stop startup instead of succeeding via `|| true`.
- PostgreSQL initialization scripts have explicit image permissions, fixing failure after privilege dropping.
- Reports and certificates use installed Unicode fonts instead of crashing on an em dash with Helvetica.
  If no supported font exists, export reports service unavailable. Native-reader PDF review remains necessary.
- Browser QA can use installed Chromium. Screenshot tooling no longer prints a TOTP enrolment secret.

## Actual results in this environment

Python 3.12.14; Node 24.22.1; PostgreSQL 16.4 image with PostGIS and pgvector.
Dependencies installed using the existing version locks; Python locks are version-pinned, not hash-locked.
An attempted hash-required install correctly refused the unhashed lock, before installation; the documented
pinned installation was then used with TLS verification. No expected checksums were changed.

| Check | Outcome |
|---|---|
| Original legacy prototype (onboarding) | 5 tests passed |
| Expanded backend baseline | 105 passed, 2 failed: FreeSerif absent, Helvetica rejected Unicode punctuation |
| Backend after privacy/PDF fixes | 109 passed in 65.81 seconds |
| Additional deployment and social regression run | 14 passed in 14.43 seconds (3 deployment cases + 11 social tests) |
| Frontend unit tests | 36 passed in 5 files |
| ESLint | Passed |
| Python ruff / mypy | Passed; mypy checked 79 source files after PDF helper |
| Next production build including TypeScript | Passed against current API |
| Playwright public/offline/social/accessibility suite | 42 passed, 3 signed-in tests skipped until accounts were provisioned |
| Playwright signed-in suite, separate run | 3 passed with synthetic local visitors: live chat/reactions, consent/review, saved itinerary |
| PostgreSQL image build and fresh initialization | Passed after permission fix |
| Alembic upgrade → downgrade base → upgrade; model drift | Passed; no new upgrade operations detected |
| PostgreSQL dump/restore into separate database | Passed; migration 0005, six destinations, PostGIS and vector verified |
| Retrieval-only evaluation | 31/34 passed: English 100%, Tigrinya 90%, Amharic 80%; 20 items are unreviewed drafts |
| Real Google accounts / institutional IdP | Unrun; issuer, client configuration and authorized test identities unavailable |
| Local model inference / voice / OCR quality | Unrun; no approved model or quality dataset supplied |
| Production load, off-site encrypted restore, disaster recovery | Unrun; local database restore is not evidence of these gates |

The first web build reached the old onboarding v0.1 service and failed on its different API response shape.
Stopping that service and running the current migrated backend resolved the build; no compatibility claim is made for v0.1 clients.

Retrieval failures: `ti-fest-01` abstained without evidence; `am-fest-01` cited the wrong document;
`am-etiq-01` abstained without evidence. A successful evaluator process does not mean all cases passed.
No generation/model-quality claim is made. Existing backend security tests include local egress-policy checks;
this is not an independent network-isolation penetration test.

## Visual QA and benchmarks

Playwright captured 1440×900 desktop and 390×844 mobile screenshots with reduced motion, under
`screenshots/validation-2026-11-13/`. Home screenshots were visually inspected: editorial serif headings,
ivory/gold surfaces, illustration explicitly labelled, and mobile menu retained. Existing green tones remain;
the requested indigo/red/gold restyling and licensed full-bleed photography are not delivered in this increment.
A navigation-arrow glyph appears as a missing glyph in this browser and remains a visual defect.
Automated accessibility checks passing does not replace screen-reader, native-language or physical-device testing.

Visit Dubai and Visit Ethiopia returned proxy CONNECT 403, so **no new live comparative benchmark was performed**.
The requester authorized internet Tigray photography. Wikimedia Commons also returned proxy CONNECT 403.
No unverifiable photograph was downloaded or committed. The existing brand files were inherited from the development
branch; their approval was not established here and they must not be used as documentary evidence.

Network draft additions: `visitdubai.com`, `www.visitdubai.com`, `visitethiopia.et`, `www.visitethiopia.et`,
`api.github.com`, `commons.wikimedia.org`, `upload.wikimedia.org`. Existing package-manager presets retained.
Saving the draft does not apply it. Review/save environment settings and publish the reusable environment as appropriate.
Re-test each destination after application; redirects/CDNs may require additional specific domains.

## Release gates and remaining implementation

| Requested area | Evidence and outstanding work |
|---|---|
| Editorial/photo design | Existing design preserved; live benchmark, licensed local photos/rights evidence, palette changes, sourced/reviewed destinations outstanding |
| Platform/identity | PostgreSQL migrations exercised; S3 backend remains an extension point; multi-provider Google linking, real IdP MFA/session integration tests and production jobs/storage operations outstanding |
| Community | Existing journals, chat, moderation, follows/blocks and consent exercised; full public/private profiles, crop flows, albums, video, feed ranking/preferences, minor protections and appeals need complete acceptance review/implementation |
| Competitions | Existing governed lifecycle exercised only in tests; real competitions/prizes/bookings remain disabled pending authorization; complete fraud/eligibility review outstanding |
| TIE/planner/offline | Retrieval, planner and browser offline flows exercised; multilingual retrieval failures remain; reranking quality, local inference, validated OCR/voice, verified travel constraints and complete offline media packs outstanding |
| Bureau | Existing console retained; complete editorial/media/provider/translation workflow acceptance and institution-specific role review outstanding |
| Production verification | Real OAuth accounts, independent security/privacy review, photo-rights verification, production performance, full backup recovery, native-speaker and manual accessibility sign-off outstanding |

No authorization to publish official content, enable prizes/bookings, award money or use government branding is inferred.

## Reproduction and deployment runbook supplement

1. Use this branch in the existing checkout. Install backend lockfiles into a Python 3.12 virtualenv and run `npm ci` in `web`.
2. Build `infra/postgres` and provision an isolated PostgreSQL server. Set generated local secrets securely, never in Git.
   Configure `DATABASE_URL` and `TEST_DATABASE_ADMIN_URL` (tests create/drop uniquely named databases).
3. Run `alembic upgrade head` from `backend`. Seed only a private development database with `python -m app.seed`.
   Start `uvicorn app.main:app`; start the worker separately for job acceptance tests.
4. From `web`, use `API_ORIGIN` for that backend, run `npm test`, `npm run lint`, `npm run build`.
   Run Playwright with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium` when using the installed browser.
   `E2E_USER_A_EMAIL`, `E2E_USER_B_EMAIL`, `E2E_PASSWORD` must refer to disposable verified local QA users.
   These are not real Google test accounts. Never run mutating suites against production.
5. Backend validation: `.venv/bin/pytest -o addopts='-p no:cacheprovider' -q`, ruff, mypy;
   run `python -m app.modules.tie.evaluation --mode retrieval_only` and inspect item failures, not just exit status.
6. On a disposable database: upgrade/downgrade/upgrade and `alembic check`. Never downgrade a live database as a smoke test.
   Restore a dump into a separate database; compare schema revision, extensions, row counts and application behavior before promotion.
7. For staging/production follow `DEPLOYMENT.md` and `BACKUP_AND_RECOVERY.md`: least-privilege runtime DB role,
   TLS, secure cookies, Redis, scanner, secrets manager, audited OIDC issuer, outbound restrictions, observability,
   encrypted off-site backups and rollback rehearsal. This increment does not provision these services.
8. Keep all release gates closed until evidence and approvals exist. Record actual results, owners and dates for every gate.

## Delivery

Small commits pushed to `feature/production-slices-validation`; no force push.
PR creation using `gh pr create` failed: POST `https://api.github.com/graphql` returned Forbidden.
The intended review base is `claude/cool-curie-tnderx` so the new hardening commits remain reviewable;
a subsequent integration into `main` must review the inherited application as well.
