# Release Readiness Assessment

Assessment date: 2026-11-12 · Branch: `claude/cool-curie-tnderx`

## Verdict: **NOT READY for production or public launch.**

The engineering foundation is suitable for **engineering review** and a **private staging pilot with synthetic data**. Public
release is blocked by institutional, legal, content and security-verification items that code alone cannot close.

## Release blockers

| # | Blocker | Type | Owner | Status |
|---|---|---|---|---|
| RB-1 | Written authorization from the Tigrai Culture and Tourism Bureau to operate as (or alongside) an official service; branding approval | Institutional | Bureau / SERK leadership | ⛔ open |
| RB-2 | Verified destination content: facts, contacts, hours, permits, accessibility, sources. All current content is development seed | Content | Bureau editors, heritage specialists | ⛔ open |
| RB-3 | Licensed photography and a rights register; custodian approvals for sacred and restricted material | Content / legal | Bureau, custodians | ⛔ open |
| RB-4 | Native-speaker review of Tigrinya and Amharic UI strings, glossary, guide refusals and the evaluation set | Language | Qualified reviewers | ⛔ open |
| RB-5 | Legal review: privacy notice and terms, retention schedule, age policy, competition rules and prize funding, heritage law | Legal | Counsel | ⛔ open |
| RB-6 | Independent penetration test and OWASP ASVS L2 verification | Security | External tester | ⛔ open |
| RB-7 | Production infrastructure: TLS/WAF, Redis, ClamAV, encrypted object storage, off-site encrypted backups, PITR, monitoring and alerts | Operations | SERK DevOps | 🟡 designed and partially rehearsed; not provisioned |
| RB-8 | Local model selection with measured quality on Bureau hardware (or launch the guide in retrieval-only mode) | AI | SERK AI + Bureau | 🟡 retrieval-only mode is ready; generation not evaluated |
| RB-9 | Manual accessibility audit (screen readers in en/ti/am, keyboard-only, low vision) and real-device mobile testing | Quality | QA + users with disabilities | 🟡 automated checks only (see test report) |
| RB-10 | Incident-response roles, contacts and a runbook drill | Operations | Bureau + SERK | ⛔ open |

## Ready for engineering review

* Backend: 96 automated tests passing, 90% line coverage; ruff, mypy and bandit clean; no known vulnerable Python dependencies.
* Migrations: apply, roll back and re-apply cleanly with no model drift.
* Security controls: identity with MFA, authorization matrix, append-only audit, least-privilege DB roles (rehearsed), egress guard (tested at socket level).
* AI: safety categories pass 100% in retrieval-only evaluation; the known cross-lingual weakness is documented.
* Operations: encrypted backup and restore rehearsed on a development database.
* Frontend: see `docs/FRONTEND.md` and `docs/TEST_REPORT.md` for build and e2e results.

## Features intentionally disabled

| Feature flag | Default | Requirement to enable |
|---|---|---|
| `bookings` | off | institutional, regulatory and operational approval; reservation implementation (not built) |
| `payments` | off | payment provider integration (not built), financial approval, PCI scope review |
| `competitions_live` | off | legal terms, funding and Bureau authorization recorded in-app + written justification |
| `public_voting` | off | approved anti-fraud design (not built) |

## Known limitations (disclosed)

* Lexical-baseline embeddings: Tigrinya and Amharic questions about non-place concepts can miss English-only sources, and one
  evaluation item cited a wrong document.
* OCR, speech, image interpretation, 3D/360 viewers and edge↔central sync are not implemented.
* S3 storage backend, editorial task management and OpenTelemetry export are not implemented.
* Docker images were not built in the authoring environment (no daemon); CI builds them.
* Load-test figures come from a 4-vCPU development host with a tiny dataset and do not represent production capacity.
