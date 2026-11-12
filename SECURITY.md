# Security Policy

## Supported versions

Only the latest commit on the active development branch receives fixes. There is **no production release** yet.

## Reporting a vulnerability

Please **do not** open a public issue. Email the SERK Technologies security contact (to be published before launch; until then use
a private GitHub security advisory on this repository) with:

* affected component and version/commit,
* reproduction steps or proof of concept,
* impact assessment.

We aim to acknowledge reports within 3 working days and to agree a disclosure timeline. Please do not access, modify or exfiltrate
other users' data, or degrade service while testing.

## Security architecture summary

* Identity: Argon2id passwords, server-side sessions, CSRF tokens, TOTP MFA required for every staff permission, OIDC (PKCE).
* Authorization: data-driven roles and permissions, object-level checks, four-eyes and conflict-of-interest rules.
* Audit: append-only, hash-chained, protected by a trigger and by database privileges.
* Input and uploads: Pydantic validation and limits; images decoded, re-encoded and metadata-stripped; malware-scan hook; quarantine.
* AI: local-first with an egress guard, permission-filtered retrieval, prompt-injection defences, an allowlisted read-only tool
  gateway, and output validation.
* Operations: least-privilege DB roles, encrypted backups, security headers/CSP, rate limiting, dependency audits, SBOM, secret scanning.

Details: `docs/THREAT_MODEL.md`, `docs/LOCAL_AI_ARCHITECTURE.md`, `docs/PRIVACY_AND_DATA_GOVERNANCE.md`.

## Incident response (outline — roles to be assigned by the Bureau)

1. **Detect:** alerts (5xx rate, rate-limit spikes, audit-chain verification failure, unexpected egress blocks), user reports.
2. **Triage** (incident lead, within 1 hour): severity, scope, and whether personal or restricted heritage data is involved.
3. **Contain:** revoke sessions (`staff.deactivate`, password reset), disable features via flags, archive or withdraw content, rotate
   `SECRET_KEY` (invalidates MFA secrets — plan re-enrolment), block egress.
4. **Eradicate & recover:** patch, restore from encrypted backups (`docs/BACKUP_AND_RECOVERY.md`), verify the audit chain.
5. **Notify:** affected users and authorities as required by law (to be confirmed by counsel).
6. **Review:** blameless post-incident report within 10 working days; update this threat model.
