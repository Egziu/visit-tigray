# Baseline Audit — Visit Tigray prototype v0.1

Audit date: 2026-11-12 · Auditor: AI engineering agent (Claude Code) · Commit audited: `63fdb83`

## 1. Repository recovery

| Step | Result |
|---|---|
| Archive `visit-tigray-serk-v0.1.zip` inspected | 25 entries under a single `visit-tigray-serk/` prefix |
| Path-traversal check | No absolute paths, no `..` segments — safe |
| Comparison with working tree | All 18 files byte-identical to the archive except `README.md` (archive README preserved as `docs/PROTOTYPE_V0.1_README.md`) |
| Git history | Preserved (`cc6ca5a`, `6fed7cb`); extraction committed as `63fdb83` |

## 2. Verified baseline

```
$ pip install -r requirements.txt && pytest -q
5 passed, 1 warning in 0.37s        (Python 3.13.18)
```

Warning: Starlette deprecation for the `httpx` test client.

## 3. Inventory

| Area | Prototype state |
|---|---|
| Backend | One 234-line FastAPI file (`app/main.py`), SQLite, raw SQL |
| Frontend | One static HTML page with ~17 lines of minified JS and 3 lines of minified CSS |
| Data | 6 seed destinations, 1 draft contest, memories, a 5-column audit log |
| AI | Optional call to an OpenAI-compatible **cloud** endpoint (`api.openai.com` by default) |
| Auth | One shared `ADMIN_TOKEN` header, compared in constant time |
| Tests | 5 smoke tests |
| Ops | Dockerfile (non-root user), single-service compose, CI that only runs pytest |

## 4. Findings

### Functional / broken workflows
- F1 "Discover the story" uses `alert()` — there are no destination detail pages.
- F2 Planner splits destinations into days by list slicing. It has no geography, time, accessibility or advisory logic. The interest ranking only sorts.
- F3 The Admin "edit destination" API exists, but the UI has no matching editor.
- F4 Contests can't be opened, entered, judged or administered (seed only).
- F5 There's no search, map, language switching, events, providers, accounts or media upload.
- F6 Memory `destination` is free text and isn't validated against real destinations.

### Architecture / technical debt
- A1 The whole monolith sits in one module that runs `init_db()` at import time, so tests depend on import order (`test_frontend.py` silently uses the default DB path).
- A2 There are no migrations; the schema lives in `CREATE TABLE IF NOT EXISTS`.
- A3 SQLite only, so there's no concurrency story, no geo or vector support, and no backups.
- A4 There's no layering (routing, domain logic and persistence are mixed) and no typed response models.
- A5 Minified, hand-written front-end assets can't be maintained.

### Security (OWASP ASVS / API Top 10 lens)
- S1 **Critical**: one shared admin token with no identity, MFA, expiry, roles or per-user audit attribution (ASVS V2/V3/V4).
- S2 **High**: the audit log has no actor, no outcome, no tamper protection and can be modified.
- S3 **High**: no rate limiting, so the memories endpoint can be spammed (API4:2023).
- S4 **High**: no security headers or CSP. Inline `onclick` in the HTML blocks a strict CSP.
- S5 **Medium**: arbitrary external `image_url` values are stored. These are tracking/hotlinking vectors, and their rights are unverifiable.
- S6 **Medium**: AI calls go to a cloud provider by default and send the visitor's question off-site, with no data-residency control.
- S7 **Medium**: the admin token lives in a DOM input (fine), but there is no CSRF model for future cookie auth.
- S8 Low: `/api/docs` is exposed unconditionally.
- Positive: parameterized SQL, Pydantic limits, HTML escaping in the client, non-root container, explicit travel disclaimers.

### Accessibility
- X1 The filter and interest chips are buttons without `aria-pressed`. Planner results lack focus management.
- X2 There's no skip link, and `alert()` dialogs make a poor screen-reader experience.
- X3 Some small text (8–9px letter-spaced labels) fails readability guidance.
- X4 Colour contrast isn't documented.

### Performance
- P1 No caching headers or pagination (memories hard-capped at 100). Assets are small (good).
- P2 A new SQLite connection is opened per request (acceptable for a prototype).

### Content / ethics
- Positive: careful advisory language, heritage-custodian caveats, and nothing published automatically.
- C1 Destination descriptions aren't sourced, have no verification dates, and are English only.

## 5. Features to preserve (and where they now live)

| Prototype feature | Preserved as |
|---|---|
| `GET /api/destinations`, `/api/destinations/{slug}` | Destination module, same paths, richer schema |
| Travel disclaimer on every plan | Planner `notice` + advisory gating |
| Rule-based plan with optional AI | Deterministic planner + TIE explanation layer |
| Consent-gated, pre-moderated memories | Community module (consent records, moderation queue) |
| Draft contest that cannot open without approvals | Awards module with enforced gates |
| Audit of admin actions | Hash-chained, append-only audit module |
| HTML escaping, parameterized SQL, input limits | Retained (React escaping, SQLAlchemy, Pydantic) |

The backlog derived from these findings is in `docs/BACKLOG.md`.
