# ADR-0001: Modular monolith on FastAPI + PostgreSQL

**Status:** accepted · 2026-11-12

**Context.** The prototype was one file. The target platform has ~15 bounded contexts, a small team, institutional hosting and
unreliable connectivity. Microservices and Kubernetes would add operational burden without a demonstrated scaling need.

**Decision.** One FastAPI codebase with modules (`app/modules/<context>`), each owning models, routes and service functions, plus a
worker process. Shared PostgreSQL with transactional consistency; side effects through an outbox (`jobs`). Re-use and modularize the
prototype's backend language (Python/FastAPI).

**Consequences.** Simple deployment (Docker Compose) and atomic cross-module operations (e.g. moderation + notification + audit in one
transaction). Modules must respect boundaries by convention (reviewed in code review). TIE inference is already out-of-process
(Ollama/vLLM), so the heaviest workload scales independently.
