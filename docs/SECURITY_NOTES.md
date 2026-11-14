# Security review — initial prototype

**Implemented:** parameterized SQL, Pydantic request validation and length limits, token-gated preview admin, constant-time token comparison, moderated memory submission, output escaping in browser, privacy consent checkbox, no secrets embedded in client, simple audit trail, explicit travel warning.

**Known gaps — block public deployment:**
- No user identities, MFA, session lifecycle, RBAC or SSO; single admin token is prototype-only.
- No rate limiting, CAPTCHA, bot prevention or abuse throttling; story submission can be spammed.
- No content-security policy, HSTS/security headers or managed TLS configuration.
- Remote image URLs are retained as text only, not downloaded, but image rights and malicious domains remain unverified.
- No data subject access/deletion workflow, formal lawful basis, retention policy or child-protection workflow.
- SQLite write serialization, no backup automation, no DB-level encryption and limited telemetry.
- No source-grounded RAG citations or independent AI safety evaluation.
- No integration with authoritative travel advisories, permission systems or national tourism booking services.
- No real contest, image upload, prize fulfillment or money movement.

**Required before institutional release:** threat model, OWASP ASVS review, accessibility testing, incident response drills, penetration testing, DPIA, custodial approval and locally applicable legal review.
