const CACHE = "aineron-v3";
const PRECACHE = ["/", "/models/", "/account/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) =>
      Promise.allSettled(PRECACHE.map((url) => c.add(url)))
    ).then(() => self.skipWaiting())
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

// Cache.put() принимает только http(s)-запросы и полные (не 206) ответы.
function cacheable(request, response) {
  return (
    request.url.startsWith("http") &&
    response.status === 200 &&
    response.type === "basic"
  );
}

function putSafe(request, response) {
  const clone = response.clone();
  caches
    .open(CACHE)
    .then((c) => c.put(request, clone))
    .catch(() => {});
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Skip: non-http(s) (chrome-extension и т.п.), non-GET, cross-origin,
  // API, admin, auth, media (Range-запросы видео/аудио дают 206)
  if (
    (url.protocol !== "http:" && url.protocol !== "https:") ||
    event.request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/admin/") ||
    url.pathname.startsWith("/users/") ||
    url.pathname.startsWith("/accounts/") ||
    url.pathname.startsWith("/media/")
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
            if (cacheable(event.request, res)) {
              putSafe(event.request, res);
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
        if (cacheable(event.request, res)) {
          putSafe(event.request, res);
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
