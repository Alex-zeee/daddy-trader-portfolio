/* Daddy Trader PWA service worker */
const CACHE = 'daddytrader-v11';
const ASSETS = [
  './',
  './index.html',
  './alexa.html',
  './fundamental.html',
  './backtest.html',
  './logo.webp',
  './favicon.png',
  './profile.webp',
  './hero-photo.webp',
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

// notification pe tap → app kholo / focus karo
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list){ if ('focus' in c) return c.focus(); }
      return clients.openWindow('./');
    })
  );
});

self.addEventListener('fetch', (e) => {
  const url = e.request.url;
  if (e.request.method !== 'GET') return;
  // doosri jagah ki requests (jaise laptop wali Alexa 127.0.0.1) ko hath na lagao
  if (!url.startsWith(self.location.origin)) return;
  // backtest ka market data (har 30 minute naya) cache mein jama na karo, warna phone/laptop ki storage bharti rehti hai
  if (url.includes('/data/')) return;
  // HTML pages + data: ALWAYS network first (fresh), fallback cache for offline
  const isData = url.includes('signals.json') || url.includes('monitor.json') || url.includes('clients.json');
  const isPage = e.request.mode === 'navigate' ||
    e.request.destination === 'document' || url.endsWith('.html');
  // data JSON: hamesha network-first (signal prices fresh hone chahiye)
  if (isData) {
    e.respondWith(
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }
  // HTML pages: pehle internet se taaza version (naya update foran nazar aaye);
  // internet na ho ya 5 second mein jawab na aaye to save kiya hua version
  if (isPage) {
    const net = fetch(e.request.url, { cache: 'no-cache', credentials: 'same-origin' }).then(res => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
      }
      return res;
    });
    net.catch(() => {});
    const slow = new Promise(r => setTimeout(r, 5000)).then(() => caches.match(e.request));
    e.respondWith(
      Promise.race([net.catch(() => caches.match(e.request)), slow.then(hit => hit || net)])
        .then(res => res || net)
        .catch(() => caches.match(e.request))
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
