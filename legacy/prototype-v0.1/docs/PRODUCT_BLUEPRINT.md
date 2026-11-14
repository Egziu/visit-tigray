# VISIT TIGRAY — Digital Destination Intelligence OS
## SERK Technologies Group · Product and Engineering Blueprint v0.1

### North star
One platform to discover, interpret, protect, share and responsibly manage Tigray's cultural and tourism heritage. Government-led content authority; local custodians approve restricted heritage content; SERK is proposed technology partner, not implied owner of Bureau records.

### 1. Product domains
1. **Discovery**: verified places, themed journeys, gallery, festivals, artisans, maps, accessibility data, operating advisories.
2. **Cultural AI concierge**: multilingual question answering, source-attributed answers, pronunciation, optional speech interaction, ability to ask follow-up questions, explicit refusal to invent opening hours or safety conditions.
3. **Intelligent planner**: preferences, mobility needs, trip duration, budgets and party composition; constraint solver over consented provider offers, verified travel conditions, ground transport links, and seasonal information. User edits suggestions and exports an itinerary.
4. **Heritage archive**: high-resolution capture, conservation status, attribution/licensing, 3D model stewardship, metadata and granular site visibility controls.
5. **Virtual travel**: remote exhibits, curator-led narratives, WebXR optional, bandwidth-friendly 2D fallback, download permissions and accessibility descriptions.
6. **Visitor memories**: text/photo/video submissions, captions, consent management, maker rights, human review, abuse reporting, deletion and archival policies.
7. **Memory awards**: themed competitions, published eligibility, local juries, accessible submissions, anti-duplicate detection, appeals, sponsor administration and audited awards ledger. Never infer an operating prize pool.
8. **Supplier marketplace**: verified guides, hotels, restaurants, transport and experiences. Bureau approval, business profiles, fraud reports and optional API integrations.
9. **Bookings and payments**: escrow or direct settlement subject to legal assessment, reconciliation, refunds, tax receipts, dispute management, cancellation and chargeback workflows, with an explicit feature gate.
10. **Bureau Studio**: accessible CMS, multilingual content workflow, versions, assets, audit trails, maps, staffing queues, service complaints, emergency content takedown and read-only executive dashboards.
11. **Research intelligence**: aggregated tourism interest trends, conservation impacts, visitor feedback analysis, exportable reports; avoid invasive behavioral profiling.
12. **Interoperability**: Ministry and Visit Ethiopia feeds only with permission, e-visa outbound official link, open standard metadata, event API and Google/Apple-compatible itinerary export.

### 2. Exemplary user journeys
**A prospective diaspora visitor:** choose Tigrinya language; learn about Aksum from approved heritage narratives; generate a heritage-focused virtual itinerary; follow references; optionally save stories; consult formal safety advisories before travel.

**A former visitor:** submit original photographs with copyright declaration; receive review confirmation; edit/delete requests; appear in public gallery only after approval; join a future fair competition with explicit rules.

**A church custodian:** review proposed descriptions/media and label restricted content; determine whether public imagery is permitted; revoke permission; see immutable access audit.

**A Bureau editor:** log in with MFA; propose description; request historical verification; escalate sensitive content; publish approved copy; observe engagement without exposing private visitor records.

**A licensed local guide:** apply with verified documents; undergo background/credential verification; update business hours and services subject to approval; respond to inquiries.

### 3. Reference production architecture
- **Frontend**: Next.js/React, server rendering for discoverability, i18n, WAI-ARIA and WCAG 2.2 AA targets; cacheable low-bandwidth images and responsive layouts.
- **Public API**: FastAPI or Go with validated schemas, scoped rate limits, API gateways and signed requests for privileged workflows.
- **Identity**: OIDC provider with MFA, passkeys, role-scoped least privilege, single Bureau organization plus tourism-partner tenancy. Public contributions require age-appropriate consent.
- **Storage**: PostgreSQL with migration pipeline, row-level permissions for organizations; S3-compatible versioned asset storage, antivirus scanning, EXIF removal, retention policies.
- **Search**: Postgres search initially, multilingual search engine when needed.
- **AI**: provider-agnostic adapter; curated heritage RAG with citations; strict tool permissions; itinerary constraint validation; multilingual evaluation and hallucination checks; human escalation.
- **Events**: outbox table + durable worker queue for moderation, email, payment events and reporting.
- **Analytics**: privacy-preserving event collection, aggregated operational dashboard and data minimization.
- **Infrastructure**: isolated dev/stage/prod, IaC, managed certificates, WAF, observability, encrypted secret storage, backup restore tests, disaster-recovery runbook.

### 4. Core data model (production)
`organizations`, `users`, `memberships`, `roles`, `permissions`, `destinations`, `heritage_assets`, `custodial_approvals`, `source_documents`, `content_versions`, `access_advisories`, `tourism_vendors`, `verified_offers`, `itineraries`, `itinerary_stops`, `visitor_memories`, `media_assets`, `consents`, `moderation_cases`, `abuse_reports`, `contests`, `contest_entries`, `judging_scores`, `awards`, `bookings`, `payments`, `refunds`, `settlement_entries`, `audit_events`, `notifications`, `data_export_requests`.

### 5. AI trust requirements
- Every historical claim links to an approved, dated source record; unresolved claims clearly marked uncertain.
- AI must not treat prompt injection in community stories as instructions.
- Source retrieval must honor custodial embargoes; sensitive coordinates remain hidden.
- A deterministic policy layer validates every proposed booked stop against verified availability, permissions, capacity, accessibility, official restrictions and transport feasibility. If feeds are unavailable, show "not verified" rather than suggesting certainty.
- Distinguish a cultural storyteller from a qualified, licensed guide. No AI impersonation of historical persons presented as factual testimony.
- Tigrinya / Amharic / English language specialists and local scholars should grade quality and respectful cultural descriptions before launch.

### 6. Community awards policy gate
**Not operational yet.** Before opening a contest: publish transparent entry criteria, jurisdictions, permitted ages, copyright/license grants, prize value and disbursement terms, selection method, independent jury, no-purchase rules where applicable, dispute procedures, privacy notice, anti-vote manipulation, platform audit report and funding authorization. Avoid gambling-like mechanics.

### 7. Governance and responsible tourism
- Joint steering group: Bureau owner, SERK engineering lead, heritage scholars, custodians, tourism businesses, accessibility and community representatives.
- Explicit rights register for every photograph, 3D scan, manuscript or oral history; revocation workflows.
- Incident manager can hide an entire location, itinerary or media item within minutes when official conditions change.
- Do not rank sacred spaces by popularity without consent; establish capacity/conservation thresholds.
- Publish transparent corrections and sources of contested historical interpretation.

### 8. Progressive delivery and acceptance gates
**P0 — prototype (this repository):** website, small editorial dataset, inspirational planner, optional server-side AI, moderated memory stories, preview admin, smoke tests.

**P1 — institutional pilot:** Bureau content workflow, staff identity/MFA, reference sources, full privacy notice, localization, real media storage, audit and content approvals. Acceptance: verified rights of 100% of published media; 100% sensitive content with custodian signoff.

**P2 — richer culture intelligence:** RAG with citations, itinerary validation, smart search, true map assets, translation QA and accessibility certification. Acceptance: curated factual QA corpus evaluation and zero unsupported live-travel promises in red-team scenarios.

**P3 — ecosystem:** licensed suppliers, vetted guides, optional bookings, payments after permits, issue escalation, reporting, contest operations after legal review. Acceptance: reconciliation tests, refund simulations, anti-fraud reviews and independent security testing.

**P4 — scale:** offline mobile clients, versioned public APIs, archive preservation, cross-institution data exchange, load testing, BCP/disaster-recovery exercises.

### 9. Operational metrics (proposed)
Verified content coverage; factual answer citation rate; user satisfaction; planning completion; accessibility issues; moderated submission turnaround; consent withdrawals fulfilled; vendors verified; complaints resolved; heritage impact warnings; monthly active visitors. Targets to be agreed by Bureau, not invented.

### 10. Non-functional acceptance
P95 API response targets determined after realistic traffic model; clean automated build; OWASP ASVS-based controls; annual penetration testing and release-specific checks; backup restore proven; 99.9% uptime target only after funded SRE operations; documented data processing agreement and disaster response.
