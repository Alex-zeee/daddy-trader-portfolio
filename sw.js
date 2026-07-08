/* Daddy Trader PWA service worker */
const CACHE = 'daddytrader-v2';
const ASSETS = [
  './',
  './index.html',
  './logo.png',
  './favicon.png',
  './profile.png',
  './hero-photo.png',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = e.request.url;
  if (e.request.method !== 'GET') return;
  // HTML pages + data: ALWAYS network first (fresh), fallback cache for offline
  const isData = url.includes('signals.json') || url.includes('clients.json');
  const isPage = e.request.mode === 'navigate' ||
    e.request.destination === 'document' || url.endsWith('.html');
  if (isData || isPage) {
    e.respondWith(
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }
  // images/static: cache first, phir network
  e.respondWith(
    caches.match(e.request).then(hit => hit ||
      fetch(e.request).then(res => {
        if (res.ok && url.startsWith(self.location.origin)) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, copy));
        }
        return res;
      })
    )
  );
});
