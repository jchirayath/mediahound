/* MediaHound service worker — makes the published catalog an installable, offline PWA.
   Strategy:
     • App shell (HTML/JS/CSS/icons/fonts): stale-while-revalidate — instant load, refreshes
       in the background so the next visit has the latest UI.
     • Catalog data (data/… + bundle.js): network-first — newest catalog when online, last
       cached copy when offline.
     • The admin write API (api/…) and any non-GET request are never touched.
   VERSION is stamped at build time (see pipeline._write_site); when it changes, the new SW
   activates, deletes old caches, and the app updates. */
const VERSION = "__MH_VERSION__";                 // build-stamped
const CACHE = "mediahound-" + VERSION;
const SHELL = [
  "./", "index.html", "identify.html", "manifest.json", "favicon.ico",
  "assets/css/styles.css", "assets/js/app.js", "assets/js/identify.js",
  "assets/img/mediahound-icon.png", "assets/img/apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => {})));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE && k.startsWith("mediahound-")).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function putCache(req, res) {
  const copy = res.clone();
  caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
  return res;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;                              // never cache writes
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;                    // only our own origin
  if (url.pathname.includes("/api/")) return;                    // admin write API → straight to network

  const isData = url.pathname.includes("/data/") || url.pathname.endsWith("bundle.js");
  if (isData) {
    // network-first: latest catalog when online, cache when offline
    e.respondWith(fetch(req).then((r) => putCache(req, r)).catch(() => caches.match(req)));
    return;
  }
  // shell & assets: stale-while-revalidate
  e.respondWith(
    caches.match(req).then((cached) => {
      const net = fetch(req).then((r) => putCache(req, r)).catch(() => cached);
      return cached || net;
    })
  );
});
