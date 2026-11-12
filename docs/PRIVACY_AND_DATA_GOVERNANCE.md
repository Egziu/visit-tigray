# Privacy and Data Governance

> **Not legal advice.** Applicable Ethiopian law on personal data, tourism, cultural heritage and competitions must be reviewed by
> qualified counsel before launch. This document describes engineering controls only. No compliance claim is made.

## 1. Data inventory

| Category | Examples | Purpose | Retention (implemented / proposed) |
|---|---|---|---|
| Account | email, display name, locale, password hash, MFA secret (encrypted) | sign-in, notifications | until deletion |
| Community content | stories, photos (EXIF stripped), comments | publication after review | until the author deletes it or moderation removes it |
| Consent records | kind, version, time, withdrawal | proof of consent | life of the account plus a legal period (to confirm) |
| Itineraries | saved plans and versions | user feature | until deletion |
| Provider inquiries | message, dates, group size | contact a provider | proposed 24 months |
| Journal posts, comments, likes | posts, comments, likes | publication after review | until the author deletes them |
| Subscriptions | subscriber ↔ publication, email-digest opt-in | delivering new-post notices | until unsubscribe |
| Space messages & reactions | chat messages, reactions | community conversation | proposed 24 months (to confirm); removed on account deletion |
| In-app notifications | title, link | notices to the user | proposed 90 days |
| Guide conversations | questions and answers | conversation context, quality | **30 days** (automatic purge) |
| Analytics events | event type, day, destination, locale, scrubbed search term | aggregate insight | proposed 25 months; **no user id, IP or session** |
| Audit log | actor, action, IP, request id | security and accountability | append-only; legal period to confirm |
| Staff data | roles, MFA | access control | until offboarding plus a legal period |

## 2. Principles applied in code

* **Minimization:** analytics are anonymous and day-granular. Search terms containing digits or `@` are dropped, and terms are
  reported only when they occur at least 3 times (k-anonymity).
* **Consent:** stories require explicit publish consent (recorded with a version). Competition entries record acceptance of the
  terms version. Client analytics are only stored when `consent: true`.
* **Purpose limitation:** messaging channels (Telegram) can receive only `aggregate`-classified reports, and only to allow-listed chats.
  Personal notifications are email only.
* **Access & portability:** `GET /api/me/export` returns all user-related data as JSON.
* **Erasure:** `DELETE /api/me` (password confirmation) deletes stories, media files, comments, itineraries and conversations, scrubs
  the account, withdraws consents and revokes sessions. Audit entries are retained (security purpose). Staff accounts are removed by an
  administrator.
* **Children:** community accounts and competitions require confirmation of age 16+. Stronger age assurance and parental consent are
  **open legal questions**.
* **Sensitive heritage:** restricted knowledge and precise coordinates are permission-gated.
* **No profiling:** recommendations come from the deterministic planner. There is no behavioural advertising and no third-party tracking.

## 3. Data residency & sovereignty

* All components can run on Bureau-controlled or approved in-country infrastructure: Docker Compose on private servers.
* In `fully_local` AI mode, no conversation, document, embedding or analytics payload is sent to external AI providers.
  This is enforced by the egress guard and tested.
* External processors are optional and off by default: the OIDC IdP (can be self-hosted Keycloak), SMTP, Telegram, and a cloud AI
  provider (which requires an admin-permitted mode with a justification).

## 4. Data subject requests (procedure)

1. The user self-serves export or deletion in the account area. Requests by other channels go to the data protection contact.
2. Verify identity (signed-in session or a verified email challenge).
3. Complete within the legal deadline (to be confirmed). Record the request in the audit log.
4. Backups: deleted data remains in encrypted backups until they rotate out (proposed 35 days). Document this in the privacy notice.

## 5. Open items

* Privacy notice and terms (Tigrinya, Amharic, English), reviewed by counsel.
* Data processing agreements with any external processor.
* Formal retention schedule approved by the Bureau.
* DPIA for the AI guide and community platform.
