# ADR-0004: Local-first AI with an enforced egress guard and extractive fallback

**Status:** accepted · 2026-11-12

**Decision.** All AI calls go through a provider abstraction. "Local" is derived from the endpoint host, never a label. A single
egress guard enforces the administrator's AI mode before any socket opens. The guide always retrieves from approved knowledge first;
generation is optional and validated; when it is unavailable the guide answers extractively with citations.

**Alternatives rejected.** Cloud-only APIs (sovereignty, cost, connectivity); unrestricted agent tool use (unsafe); answering without
retrieval (hallucination risk).

**Consequences.** The platform is useful with zero model downloads. Generation quality depends on model evaluation still to be done
on Bureau hardware.
