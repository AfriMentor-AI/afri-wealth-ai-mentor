// AfriMentor AI — Service Worker (G1.4: PWA app-shell caching + offline fallback)
//
// STRATEGY
// - App shell (HTML routes, manifest, icons): cached on install, served
//   network-first with cache fallback. This is what makes the app open
//   at all when offline instead of a browser error page.
// - Static build assets (_next/static/*): cache-first, since these are
//   content-hashed and immutable — once cached, never worth re-fetching.
// - Everything else: network-first, falling back to cache if present.
//
// HONEST NOTE ON "OFFLINE DATA": today all of chat/goals/library/progress
// content comes from lib/mockData.ts, which is compiled INTO the JS
// bundle — there's no separate network call for it. That means once the
// app shell is cached, those screens don't just show a fallback offline
// state, they actually work fully offline, because the "data layer" is
// already sitting in the cached JS. That stops being true the moment
// G1.3's real API is live — at that point this service worker will also
// need to cache API responses (e.g. via a runtime cache + background
// sync for POSTs) to keep this same guarantee. Flagging now so it's not
// a surprise regression later.

const CACHE_VERSION = "afrimentor-shell-v1";
const OFFLINE_URL = "/offline.html";

// Routes worth precaching as the app shell. Static Next.js build assets
// (_next/static/*) are intentionally NOT listed here — their filenames
// are content-hashed per build, so precaching them by name would go
// stale immediately. They're instead cached opportunistically the first
// time each is requested (see the fetch handler below), which is
// resilient to hash changes across deploys without needing a build step
// to regenerate this list.
const APP_SHELL_ROUTES = [
  "/",
  "/welcome",
  "/intake",
  "/persona",
  "/chat",
  "/goals",
  "/goals/action",
  "/library",
  "/progress",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  OFFLINE_URL,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      // addAll fails the whole install if ANY single URL 404s — use
      // individual add() calls so one missing/renamed route doesn't
      // silently break shell caching for every other route.
      Promise.allSettled(APP_SHELL_ROUTES.map((url) => cache.add(url)))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function isStaticAsset(url) {
  return url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/");
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // never cache mutating requests
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // don't touch cross-origin (fonts CDN etc.)

  if (isStaticAsset(url)) {
    // Cache-first: content-hashed, immutable, safe to trust the cache forever.
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
            return response;
          })
      )
    );
    return;
  }

  // Navigations and everything else: network-first, falling back to
  // cache, falling back to the offline shell as a last resort so the
  // user NEVER sees a bare browser "no internet" error page.
  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === "navigate") {
          const shellFallback = await caches.match(OFFLINE_URL);
          if (shellFallback) return shellFallback;
        }
        return Response.error();
      })
  );
});
