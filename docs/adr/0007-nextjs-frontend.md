# ADR-0007: Next.js (App Router, TypeScript, Tailwind) for the public site and Bureau console

**Status:** accepted · 2026-11-12

**Decision.** Replace the prototype's static page with a Next.js app that server-renders public pages (SEO, low-bandwidth first
paint), proxies `/api/*` to FastAPI (same-origin cookies, CSRF), externalizes all strings to `messages/{en,ti,am}.json` and ships a
hand-written service worker for offline use. The Bureau console is a separate route tree with its own layout and is never cached
offline.

**Consequences.** Two runtimes (Python, Node) to operate. Splitting the console into a separate deployable later is straightforward
because it shares no server code with the public tree.
