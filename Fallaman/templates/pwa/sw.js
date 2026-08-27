const CACHE = "fallaman-shell-v4";
const PRECACHE = [
  "/",
  "/hors-ligne/",
  "/static/css/fallaman.css",
  "/static/js/app.js",
  "/static/vendor/bootstrap.min.css",
  "/static/vendor/bootstrap-icons.min.css",
  "/static/vendor/bootstrap.bundle.min.js",
  "/static/vendor/htmx.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Never cache or intercept uploaded media (avatars, listing photos).
  if (url.pathname.startsWith("/media/")) return;

  const privatePath = [
    "/messages/",
    "/tableau-de-bord/",
    "/admin/",
    "/connexion/",
    "/notifications/",
    "/profil/",
    "/verifier/",
  ];
  if (privatePath.some((path) => url.pathname.startsWith(path))) return;

  // Static assets: network first, cache fallback (avoid stale broken CSS).
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // HTML navigations only: network first, offline page if needed.
  if (request.mode === "navigate" || request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(request).then((cached) => cached || caches.match("/hors-ligne/"))
      )
    );
  }
});
