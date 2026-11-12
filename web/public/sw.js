/* Visit Tigray service worker — hand-written, no build step.
 *
 * Policy (see docs/FRONTEND.md "Offline"):
 *  - Precache the app shell (offline page for each locale, manifest, icon).
 *  - HTML navigations: network-first, fall back to cached copy, then to /{locale}/offline.
 *  - Public read APIs (/api/destinations*, /api/events, /api/advisories, /api/categories):
 *    stale-while-revalidate.
 *  - NEVER cache: /api/me, /api/auth, /api/bureau, /api/tie, /api/media uploads, any non-GET,
 *    any /{locale}/bureau or /{locale}/account page (private or staff data on shared devices).
 */
const VERSION = "v1";
const SHELL = `vt-shell-${VERSION}`;
const PAGES = `vt-pages-${VERSION}`;
const API = `vt-api-${VERSION}`;
const LOCALES = ["en", "ti", "am"];
const PRECACHE = [...LOCALES.map((l) => `/${l}/offline`), "/manifest.webmanifest", "/icons/icon-192.png", "/brand/visit-tigray-logo-520.webp"];

const PRIVATE_PAGE = /^\/(en|ti|am)\/(bureau|account)(\/|$)/;
const NEVER_CACHE_API = /^\/api\/(me|auth|bureau|tie|itineraries|shared-itineraries)(\/|$)/;
const SWR_API = /^\/api\/(destinations|events|advisories|categories|config\/public)(\/|$|\?)/;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((c) => Promise.all(PRECACHE.map((u) => c.add(new Request(u, { cache: "reload" })).catch(() => undefined))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("vt-") && !k.endsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function localeOf(pathname) {
  const m = /^\/(en|ti|am)(\/|$)/.exec(pathname);
  return m ? m[1] : "en";
}

async function networkFirstPage(request) {
  const url = new URL(request.url);
  try {
    const res = await fetch(request);
    if (res.ok && !PRIVATE_PAGE.test(url.pathname)) {
      const copy = res.clone();
      caches.open(PAGES).then((c) => c.put(request, copy));
    }
    return res;
  } catch {
    const cached = await caches.match(request, { ignoreSearch: false });
    if (cached) return cached;
    const fallback = await caches.match(`/${localeOf(url.pathname)}/offline`);
    return fallback || new Response("Offline", { status: 503, headers: { "content-type": "text/plain" } });
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(API);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((res) => {
      if (res.ok) cache.put(request, res.clone());
      return res;
    })
    .catch(() => undefined);
  return cached || (await network) || new Response(JSON.stringify({ error: { code: "offline", message: "Offline and not cached" } }), { status: 503, headers: { "content-type": "application/json" } });
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    if (NEVER_CACHE_API.test(url.pathname)) return;
    if (SWR_API.test(url.pathname)) event.respondWith(staleWhileRevalidate(request));
    return;
  }
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((res) => {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(request, copy));
            return res;
          }),
      ),
    );
    return;
  }
  if (request.mode === "navigate") {
    if (PRIVATE_PAGE.test(url.pathname)) return; // straight to network, never cached
    event.respondWith(networkFirstPage(request));
  }
});

// "Save for offline" asks us to cache specific public pages.
self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "cache-urls" && Array.isArray(data.urls)) {
    event.waitUntil(
      caches.open(PAGES).then((c) =>
        Promise.all(
          data.urls
            .filter((u) => typeof u === "string" && u.startsWith("/") && !PRIVATE_PAGE.test(u))
            .map((u) => fetch(u).then((res) => (res.ok ? c.put(u, res) : undefined)).catch(() => undefined)),
        ),
      ),
    );
  }
});
