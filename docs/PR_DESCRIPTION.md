Continue the existing implementation from `claude/cool-curie-tnderx` (313443f) with social privacy and deployment fixes. Main still contains the v0.1 archive; the existing development branch already contains the expanded application, so no archive was extracted over it.

- Apply message visibility rules to reply previews; revalidate session, roles and blocks while streaming; redact hidden updates and avoid dropping update batches.
- Make Compose migrations fail closed and make database init scripts readable after the PostgreSQL entrypoint drops privileges.
- Support the installed Chromium for browser QA and remove MFA-secret logging from the screenshot script.
- Use installed Unicode fonts for report/certificate PDF export rather than a Latin-1 fallback that crashes on typographic punctuation.

This is an engineering hardening increment, not completion of all requested production features or a production readiness claim. Validation results, remaining scope, and deployment gates are recorded in docs/VALIDATION_2026-11-13.md.
