# ADR-0008: Server-Sent Events (not WebSockets) for real-time Spaces

**Status:** accepted · 2026-11-12

**Context.** Spaces need live message delivery. The web tier proxies `/api/*` to FastAPI through Next.js rewrites, so that browser
cookies, CSRF and CSP stay same-origin. The API runs several worker processes, and may run several replicas.

**Decision.** Use Server-Sent Events from `GET /api/spaces/{space}/channels/{channel}/stream?after=<id>`. Each stream reads new
messages and update events (edits, reactions, removals via a global `space_message_update_seq`) from PostgreSQL every 1.5 s,
sends a heartbeat every 15 s, and closes after ~55 s with a `reconnect` event so clients resume with `?after=`. Posting stays
plain HTTPS POST (with CSRF and rate limits).

**Why.** SSE passes through HTTP proxies and Next.js rewrites unchanged. It reuses session cookies and needs no extra
authentication handshake. Because state comes from the database rather than a process-local broker, it works across workers
and replicas without Redis. The browser `EventSource` reconnects automatically.

**Consequences.** Delivery latency is roughly the poll interval (≤ ~1.5 s), and each open stream holds a worker thread. That is
fine for pilot scale. At larger scale, replace polling with PostgreSQL `LISTEN/NOTIFY` or Redis pub/sub behind the same endpoint
contract, and/or move streams to a dedicated service.
