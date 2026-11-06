/* Service worker : met tous les fichiers en cache pour fonctionner hors ligne. Version 767d398f1e. */
const V = 'codage-live-767d398f1e';
const FILES = ["./", "css/style.css", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "index.html", "js/backup.js", "js/chart.js", "js/clock.js", "js/config.js", "js/events.js", "js/input.js", "js/pitch.js", "js/pwa.js", "js/stats.js", "js/sync.js", "js/ui.js", "js/viz.js", "manifest.webmanifest"];
self.addEventListener('install', function (e) { e.waitUntil(caches.open(V).then(function (c) { return c.addAll(FILES); }).then(function () { return self.skipWaiting(); })); });
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== V; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(function (r) { return r || fetch(e.request); }));
});
