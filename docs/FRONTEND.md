# Frontend — Visit Tigray web (`web/`)

Next.js 16.4.6 (App Router, Turbopack) · React 19.3 · TypeScript (strict) · Tailwind CSS 4.3.
Public tourism site, PWA and Bureau console in one app; all data comes from the FastAPI backend.

## Run it

```bash
cd web
npm ci
# API_ORIGIN is read at BUILD time for the /api rewrite and at RUN time for server fetches.
API_ORIGIN=http://localhost:8000 npm run build
API_ORIGIN=http://localhost:8000 npm start          # http://localhost:3000 -> redirects to /en
npm run dev                                          # development (API_ORIGIN defaults to :8000)
```

Optional: `NEXT_PUBLIC_MAP_STYLE_URL` = a **licensed** MapLibre style URL. Without it the map renders an
accessible schematic plot + list, and no third-party tiles are requested.

Quality gates:

```bash
npm run lint        # ESLint (next + react-hooks rules)
npm run typecheck   # tsc --noEmit
npm test            # Vitest unit tests
npm run e2e         # Playwright; needs a production build + running API with `python -m app.seed`
```

## Architecture

| Area | Location | Notes |
|---|---|---|
| Locale routing | `proxy.ts`, `app/[locale]/` | `/` → `/{en,ti,am}` from cookie/Accept-Language. `[locale]/layout.tsx` is the root layout (sets `<html lang>`). Unknown paths → `[...rest]` → localized `not-found`. |
| Strings | `messages/{en,ti,am}.json`, `lib/i18n.ts` | Every UI string is externalized. `ti`/`am` carry `_meta.status = "machine-draft, requires native-speaker review"`, and non-English pages show a visible "Translation under review" notice. A test enforces key and `{placeholder}` parity. |
| Design system | `app/globals.css`, `components/ui/` | Tokens as CSS variables (ivory, sandstone, earth, olive, deep forest) for light/dark/system themes. Base styles live in `@layer base` so utilities win. Self-hosted fonts via `@fontsource` (Inter, Cormorant Garamond, Noto Sans/Serif Ethiopic), so there is no font CDN at runtime. Motion is gated by `prefers-reduced-motion`. |
| API access | `lib/api.ts` (browser), `lib/server-api.ts` (server) | Browser calls go same-origin through the `/api/*` rewrite, so session cookies stay HttpOnly. Unsafe methods send `x-csrf-token` from the `vt_csrf` cookie. API errors `{error:{code,message}}` are shown to users verbatim. Server fetches never throw: pages render an honest "service unavailable" state. |
| Public site | `app/[locale]/(site)/…` | Home, destinations (+detail), map, events, advisories, travel prep, guide, plan (+shared), memories (+detail/new), creators, awards, providers, account (+verify/reset), offline, about. |
| Bureau console | `app/[locale]/bureau/…`, `components/bureau/` | Separate layout with a role-aware sidebar (from `/api/me` permissions), global page/destination search, and sign-in and MFA gates. Not indexed and never cached by the service worker. |
| PWA | `public/sw.js`, `public/manifest.webmanifest`, `lib/offline.ts`, `components/site/pwa.tsx` | See below. |

### Honesty rules implemented in the UI
- Unknown facts (visit duration, permits, step-free access, terrain, facilities, travel time) are displayed as **Unknown**, never inferred.
- Every destination shows its verification state ("Not yet verified", "Last verified …", "Information may be out of date"), its synthetic-data label and its translation status (machine drafts are labelled).
- Imagery: there are no photographs in the codebase. Decorative SVGs are `aria-hidden` and labelled "Illustration". API media render with credit, licence and Illustration/Reconstruction/AI-generated badges.
- Guide answers show confidence, whether a local model, an external provider or retrieval-only produced them, numbered citations linked to sources, and a "verify official information" note.
- Awards show "Not yet open — pending authorization/funding" and never invent prizes. Providers show "Reservations are not available" while the `bookings` flag is off.
- The Bureau dashboard shows only counts returned by the API. A tile the user's role cannot read is hidden, not faked.
- Planned endpoints that aren't deployed render "not available yet" rather than mock data.

### Rendering strategy
`cacheComponents` is **off** (`next.config.ts`). Public pages use fetch revalidation (60 s), and the build
does not need a reachable API. Destination detail and search-driven pages render on demand.

## Offline / PWA
- `sw.js` (hand-written, no build step) behaves as follows:
  - **Precache:** the offline page for each locale, the manifest and the icon.
  - **Pages:** network-first, falling back to a cached copy, then to `/{locale}/offline`.
  - **Public APIs:** stale-while-revalidate for `/api/destinations*`, `/api/events`, `/api/advisories`, `/api/categories` and `/api/config/public`.
  - **Never cached:** `/api/me`, `/api/auth`, `/api/bureau`, `/api/tie`, `/api/itineraries`, `/{locale}/bureau`, `/{locale}/account`, and any non-GET request.
- **Save for offline** (destinations, itineraries) stores the data in IndexedDB with `savedAt` and asks the service worker to cache the page.
- The **offline library** (`/{locale}/offline`) lists saved items with their saved date, opens them without a network, shows storage used versus quota, and has "clear all" plus a data-saver toggle.
- **Outbox:** text-only memory drafts are queued in IndexedDB while offline and sent on the `online` event. Photo uploads require connectivity and the UI says so.

## Test results (real runs, 2026-11-12)

Run against the backend at commit `9c675dd` with the development seed (6 synthetic destinations, 9 knowledge documents) on PostgreSQL 16, in headless Chromium 1243.

| Check | Result |
|---|---|
| `npm run lint` | 0 problems |
| `npm run typecheck` | pass |
| `npm run build` | pass (all routes compiled) |
| `npm test` (Vitest) | **24 passed** (3 files: API helper incl. CSRF and error parsing, i18n completeness and placeholders, formatting) |
| `npm run e2e` (Playwright) | **30 passed** (34.7 s) |

E2E coverage:
- **Locales:** `/` redirect; home in en/ti/am with `lang` and the review notice.
- **Destinations:** list and detail with sources, the synthetic label and explicit unknowns; cross-lingual search (`ኣክሱም`, `Axum`, `aksum`); Tigrinya detail.
- **Accessibility:** skip link; **axe (WCAG 2.0/2.1/2.2 A+AA) with no serious/critical violations** on 10 pages (home en/ti, destination, am list, plan, guide, map, account, bureau, offline).
- **Mobile:** no horizontal scroll at 390×844 on 6 pages; the mobile menu works.
- **Live API:** guide answer with citations, `[n]` links and provenance; planner day plan with reasons and notice.
- **Bureau:** sign-in gate.
- **Offline:** cached destination page and offline library work with the network disabled; private pages and APIs are never present in caches.

Defects found and fixed during testing:
1. Unlayered base CSS (`a { color: inherit }`) overrode Tailwind utilities, dropping contrast to 1.11:1 on button links. Base styles moved into `@layer base`.
2. The destination route combined an empty `generateStaticParams` with the parent's `dynamicParams=false`, so every slug 404'd.
3. Unmatched locale paths rendered Next's bare 404 without `lang`. Fixed with a localized `[...rest]` catch-all and `not-found`.
4. The guide crashed after an answer: modern `scrollIntoView()` returns a Promise, which an expression-bodied `useEffect` returned as its "cleanup".
5. The SVG map used `role="img"` while containing links (nested-interactive). Changed to `role="group"`.

Screenshots (deviceScaleFactor 2) are in `docs/screenshots/`: `home.png`, `destination-detail.png`, `guide.png`, `bureau-dashboard.png`, `bureau-destinations.png`. Regenerate them with `node scripts/screenshots.mjs ../docs/screenshots`.

## Known gaps / follow-ups
- **CSP** allows `'unsafe-inline'` scripts because Next injects inline bootstrap code. Nonce-based CSP through `proxy.ts` is a follow-up.
- **Translations:** Tigrinya and Amharic strings are machine-assisted drafts and **must be reviewed by qualified native speakers** before launch.
- **API_ORIGIN for rewrites is baked in at build time.** Container images need it as a build argument, or a runtime proxy route.
- **No signed-in E2E flows yet** for memories, itineraries or Bureau editing. They need test accounts with TOTP; the screenshot script shows the approach. Bureau screens were exercised manually.
- **Offline maps** aren't implemented (tile licensing). The schematic map is a list, not a cartographic product.
- **Ge'ez rendering** relies on Noto Ethiopic web fonts and wasn't validated on low-end Android devices.
- **Analytics** renders whatever series the API returns as tables with inline bars. There are no chart-library visualisations yet.
- **Backend observations from integration**, for the backend owner:
  - TIE citation excerpts sometimes start mid-word, e.g. "gdom of Aksum…".
  - `/api/tie/status` reports the Ollama model as the provider even when Ollama is unreachable; answers then fall back to retrieval-only, which the UI labels correctly.
