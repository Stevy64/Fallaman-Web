const CACHE = "fallaman-shell-v6";
const PRECACHE = [
  "/hors-ligne/",
  "/static/css/fallaman.css",
  "/static/js/app.js",
  "/static/vendor/bootstrap.min.css",
  "/static/vendor/bootstrap-icons.min.css",
  "/static/vendor/bootstrap.bundle.min.js",
  "/static/vendor/htmx.min.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      await Promise.all(
        PRECACHE.map((url) => cache.add(url).catch(() => undefined))
      );
      return self.skipWaiting();
    })
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
  if (url.origin !== self.location.origin) return;

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

  if (request.mode === "navigate" || request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(request).then((cached) => cached || caches.match("/hors-ligne/"))
      )
    );
  }
});
