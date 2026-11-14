# Test Plan — Visit Tigray 2.0

What we test, where, by whom and when it counts as passed. Results go in `docs/TEST_REPORT.md`, with only output that was
actually produced (CLAUDE.md rule 12).

## 1. Goals

1. The platform works end to end for its four kinds of user: **visitor**, **community member**, **Bureau staff** and **administrator**.
2. Security and privacy rules hold: authorization, MFA, audit, protected heritage coordinates, egress control, data export and erasure.
3. The AI guide stays honest. It cites sources, refuses restricted knowledge, says "unknown" instead of guessing, and never decides feasibility.
4. The platform works in Tigrinya, Amharic and English, on low-end phones, on slow networks and offline.

## 2. Test levels and where they run

| Level | Tool | Where | When | Status today |
|---|---|---|---|---|
| Backend unit, integration and API | pytest on real PostgreSQL + PostGIS + pgvector | local, CI | every push | **107 passing** |
| Authorization matrix (every route, allowed and denied) | `tests/test_authz_matrix.py` | local, CI | every push | passing |
| Frontend unit | Vitest | local, CI | every push | **36 passing** |
| Browser end to end | Playwright + axe (Chromium) | local (`npm run e2e`) | before each merge | **45 passing** |
| AI evaluation | `python -m app.modules.tie.evaluation` | local, CI | every push and every model or prompt change | 31/34 retrieval-only |
| Static security | ruff, mypy, bandit, pip-audit, npm audit, gitleaks | CI | every push | clean |
| Migrations | upgrade → downgrade → upgrade → `alembic check` | CI | every push | passing |
| Load | Locust | staging | before release | baseline only (local) |
| Staging smoke | manual checklist §4 | Railway staging | after every deploy | **blocked**: staging secrets not set |
| User acceptance (UAT) | scripted sessions §6 | staging | before release | not started |
| Penetration test | independent tester | staging | before public launch | not started |

## 3. Environments

| Environment | Data | Who |
|---|---|---|
| Local / CI | throwaway database, synthetic seed (`python -m app.seed`) | developers |
| **Staging** (Railway, `visit-tigray-staging`) | synthetic seed only, **no real personal data** | developers, testers, Bureau reviewers |
| Production | none yet; requires Bureau authorization | — |

Test accounts are synthetic (`@example.org`). Passwords are kept in a password manager and never in git, tickets or chat.

## 4. Staging smoke test (after every deploy, ~15 min)

**Prerequisite:** the Railway shared variables `POSTGRES_PASSWORD`, `VT_APP_PASSWORD`, `VT_MIGRATOR_PASSWORD` and `SECRET_KEY` are
set, and the `db`, `api`, `worker` and `web` services are all green.

| # | Check | Expected |
|---|---|---|
| S1 | `GET /api/health` | 200; database, migrations and AI mode reported |
| S2 | Home in `/en`, `/ti` and `/am` | correct language, `lang` attribute set, the "not an official service" notice is visible |
| S3 | Destinations list and detail | synthetic label shown; unknown fields say "unknown" |
| S4 | Search `ኣክሱም`, `Axum`, `aksum` | all three find Aksum |
| S5 | AI Guide question | answer has numbered citations that link to sources |
| S6 | Planner: 3 days, 2 destinations | deterministic plan with reasons, checklist and advisory notice; same input gives the same output |
| S7 | Register, verify email, sign in | session works; a weak password is rejected |
| S8 | Spaces: two browsers in one channel | "Live" badge; message and reaction appear without reload |
| S9 | Journal: write a story | consent is required; the story shows "Awaiting review" and is not public |
| S10 | Bureau sign-in as staff | TOTP MFA required before any staff tool opens |
| S11 | Moderator approves the story | story becomes public; subscribers notified once; an audit event is written |
| S12 | Offline: load a destination, go offline, reload | cached page and offline library work |
| S13 | Feature flags | bookings, payments, public voting and live competitions are **off** |

## 5. Functional test cases by area

Each area needs automated coverage of its main path **and** its main failure path. **Bold** marks gaps to close.

| Area | Main path | Failure / abuse cases |
|---|---|---|
| Identity | register, verify, login, MFA, OIDC, logout, reset | lockout after failed attempts, CSRF missing, expired session, staff without MFA |
| Roles / RBAC | each role can do its tasks | each role is **denied** others' tasks (authz matrix) |
| Destination CMS | draft → review → publish → rollback; schedule | live page stays up while a draft is pending; translator cannot approve own translation |
| Heritage protection | heritage staff see exact coordinates | public sees coarsened or hidden coordinates; restricted knowledge never reaches the AI for the public |
| Media | upload, re-encode, EXIF/GPS stripped | wrong type, oversize, polyglot file, external URL rejected |
| Knowledge Vault | upload → second-person review → publish → withdraw | same person cannot approve; withdrawn document leaves the guide immediately |
| AI Guide | cited answers in en/ti/am | prompt injection in documents and questions, restricted topics, "fully local" mode makes **zero** external calls |
| Planner | feasible plans, alternatives, ICS/PDF export | region-wide "travel not advised" advisory stops travel routes; impossible constraints explained, not faked |
| Journals | write, subscribe, like, comment, notify | unconsented submission, held content, report, blocked user |
| Spaces | join, post, react, reply, live stream | slow mode, ban cannot be bypassed by rejoining, held messages visible only to author and moderators |
| Memories / community | submit with consent, moderation, appeal | appeal decided by a different moderator |
| Privacy | data export includes social content | account erasure removes journals, messages, subscriptions |
| Providers / awards | provider verification; competition setup | four-eyes approvals enforced; feature flags off |
| Analytics / reports | CSV, Excel, PDF exports | "engagement ≠ visitor arrivals" note always present |
| Audit | every privileged change recorded | rows cannot be updated or deleted (DB trigger); hash chain verifies |
| **Bureau console browser tests** | **editing, publishing, moderation in the browser** | **currently API-tested only** |

## 6. User acceptance testing (UAT)

Participants: 2 Bureau content editors, 1 heritage specialist, 1 moderator, 1 translator per language (ti, am) and 5 visitors
(including diaspora and at least 2 on low-end Android phones).

Each participant gets a task script based on `docs/BUREAU_USER_GUIDE.md`, for example "update a destination's opening
information, mark it verified, and publish". We record task success, time, errors and comments.

**Pass:** at least 80% task success, no blocker defects, and native speakers approve the reviewed translations.

## 7. Non-functional testing

| Type | Target | Method |
|---|---|---|
| Performance | p95 < 300 ms for public pages and API reads on staging | Locust, 100 users, multiple source IPs |
| AI latency | guide answer p95 < 8 s with the chosen local model | measured once model weights and GPU are available |
| Accessibility | WCAG 2.2 AA: 0 serious/critical axe issues, plus manual screen-reader passes (NVDA, TalkBack) in en/ti/am | axe + manual |
| Mobile / low bandwidth | usable at 390×844 on a slow 3G profile | Playwright throttling + real devices |
| Backup / restore | restore of a staging dump with matching row counts | `scripts/` rehearsal, monthly |
| Security | OWASP ASVS L2 checklist; independent penetration test | before public launch |

## 8. Defect handling

| Severity | Meaning | Release rule |
|---|---|---|
| Blocker | data loss, security or privacy breach, fabricated facts shown as verified | must be fixed |
| Major | a main user task cannot be completed | must be fixed or explicitly accepted by the product owner |
| Minor | workaround exists | may ship, tracked in `docs/BACKLOG.md` |

Every fixed defect gets a regression test.

## 9. Exit criteria for a release candidate

1. All automated suites green in CI on the release commit.
2. Staging smoke test §4 fully passed on that commit.
3. UAT pass criteria §6 met.
4. No open Blocker defects; Major defects fixed or signed off.
5. Penetration test findings rated high or critical are fixed.
6. `docs/TEST_REPORT.md` and `docs/RELEASE_READINESS.md` updated with real results.
7. Written Bureau authorization before any public "official" launch.

## 10. Order of work (next steps)

1. **Unblock staging:** set the four Railway shared variables, redeploy db → api/worker, then run the smoke test §4.
2. Add Bureau console browser tests (editing, publishing, moderation) and add the e2e job to CI.
3. Run load tests against staging from several source IPs.
4. Prepare the UAT scripts and recruit participants.
5. Do manual screen-reader and real-device passes.
6. Commission the independent penetration test.
