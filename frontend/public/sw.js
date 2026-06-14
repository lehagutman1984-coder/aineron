const CACHE = "aineron-v1";
const PRECACHE = ["/", "/catalog/", "/account/", "/api-docs/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Skip: non-GET, API, admin, auth
  if (
    event.request.method !== "GET" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/admin/") ||
    url.pathname.startsWith("/users/") ||
    url.pathname.startsWith("/accounts/")
  ) {
    return;
  }

  // Next.js static chunks: cache-first (they're content-hashed)
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      caches.match(event.request).then(
        (cached) =>
          cached ||
          fetch(event.request).then((res) => {
            if (res.ok) {
              caches.open(CACHE).then((c) => c.put(event.request, res.clone()));
            }
            return res;
          })
      )
    );
    return;
  }

  // Pages: network-first, fallback to cache, then /
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.ok) {
          caches.open(CACHE).then((c) => c.put(event.request, res.clone()));
        }
        return res;
      })
      .catch(() =>
        caches
          .match(event.request)
          .then((cached) => cached || caches.match("/"))
      )
  );
});
