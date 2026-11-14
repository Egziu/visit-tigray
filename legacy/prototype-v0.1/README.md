# Visit Tigray · SERK Technologies Group

**A working, editorial-first digital tourism prototype** featuring a responsive premium visitor site, curated destinations, a personalized discovery planner with optional AI, human-moderated visitor memories, a draft awards model and an administrative review console.

> Status: **working initial release, NOT a production-ready government platform or an approved travel service**. This is an independently built proposal prototype; it is not an official site of the Tigrai Culture and Tourism Bureau.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env      # On Windows, copy manually
# Edit .env and set ADMIN_TOKEN to a strong secret
set -a; source .env; set +a  # POSIX only
uvicorn app.main:app --reload
```

Open http://localhost:8000. API docs: http://localhost:8000/api/docs.

Or run `docker compose up --build` after preparing `.env`.

## Working features

- Mobile-responsive editorial visitor website in deep green, sand and warm cream.
- 6 sample destinations; Bureau-edited destination descriptions and advisories.
- Cultural discovery itinerary generator (curated-rule mode; no invented live availability).
- Optional AI enrichment via an OpenAI-compatible completions API (`AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`). AI is server-side only.
- Visitor stories with explicit consent and **pending → approved/rejected** review; only approved entries are publicly visible.
- Editorial audit log, moderation queue, basic Bureau dashboard and curated contest draft.
- Input validation, SQL parameterization, HTML escaping, no stored secrets, test suite, Docker and CI.

## Critical boundaries

- Never publish actual religious-site digital replicas, restricted photography or detailed archaeological datasets without steward/custodian permission.
- No claim of safe roads, access, operating sites, bookings or confirmed travel. All travel details require official verification.
- No money collection, awards issuance, public prize voting or contest enrollment until legal rules, sponsor funding, eligibility, age limits, fairness, fraud protection and privacy notices are approved.
- Admin token is **preview-only** authentication. Replace with institution-grade OIDC, MFA, scoped RBAC, session management and CSRF protection before launch.
- Story image links are not uploaded media or reviewed for safety; production requires object storage, signed uploads, antivirus checks, rights review, EXIF stripping and automated abuse detection.
- Improve CSP, request throttling, anti-spam, data retention and deletion, observability, encryption/backup procedures, penetration tests and accessibility audits prior to public launch.

## Recommended production roadmap

**Foundation:** interviews, cultural stewardship council, official content rights, multilingual copy (Tigrinya, Amharic, English), CMS, accessibility and secure staff identity.

**Experience intelligence:** place-based RAG grounded in curator-approved sources, citations, multilingual speech guide, explainable itinerary ranking, verified advisory feeds and user feedback.

**Community:** consented media upload, attribution, copyright takedown, moderation automation with humans deciding, contest eligibility, anti-bot voting, independent judging, prize sponsor accounting.

**Tourism operations:** verified tourism vendor registry, licensing interfaces, service quality evidence, reservation integrations only after approval, permissions and refunds, secure payments and financial reconciliation.

**Government intelligence:** multi-department dashboards, tourism impact and conservation indicators, data export, open standards and vendor interoperability.

## Data and deployment

SQLite is used for local preview only. For government production migrate to PostgreSQL, object storage, separate worker queue and managed encrypted backups. Host under an approved domain after Bureau authorization. Keep `ADMIN_TOKEN` secret and ensure the deployed service is HTTPS-only.

## Research references

- Visit Ethiopia: https://visitethiopia.et/
- Experience Abu Dhabi AI guide: https://visitabudhabi.ae/en/plan-your-trip/essential-info/ask-abu-dhabi
- Tourism New Zealand: https://www.newzealand.com/

© 2026 SERK Technologies Group. Prototype for evaluation and co-design.
