# ADR-0009: Keep Python (FastAPI) + TypeScript (Next.js); no rewrite into another language

**Status:** accepted · 2026-11-12

**Context.** Stakeholders asked for "the best, most solid and secure programming language".

**Decision.** Keep Python 3.12 (typed, `mypy`-checked) for the backend and strict TypeScript for the frontend.

**Rationale.**
* The platform's security properties come from **design and verification**, not syntax: server-side authorization with an
  automatic authorization-matrix test, MFA, an append-only hash-chained audit log, least-privilege database roles, an egress
  guard, typed request validation (Pydantic), and structured content instead of HTML. All of these are tested (106 backend tests).
* The dominant web-application risks (OWASP Top 10: broken access control, injection, SSRF, auth failures) are logic and
  configuration flaws that a memory-safe language does not prevent. Python and TypeScript are already memory-safe.
* The AI/geo ecosystem (pgvector, PostGIS bindings, PDF and image processing, model clients) is strongest in Python.
* A rewrite would discard tested behaviour and delay institutional review.

**When to revisit.** If a hot path is proven CPU-bound (e.g. high-throughput embedding or media processing), extract that one
component as a separate service (Rust or Go), keeping the same API contract.
