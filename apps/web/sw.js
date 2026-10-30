// Offline APP SHELL only. Never store auth, notes or any API response in CacheStorage.
const CACHE = 'vainah-messenger-v081';
const ASSETS = ['/', '/assets/app.js', '/assets/suite-ui.js', '/assets/messenger-live.js', '/assets/styles.css', '/assets/icon-192.png', '/assets/messenger-home.css', '/assets/messenger-app.js'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(Promise.all([caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))), self.clients.claim()]));
});
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin || new URL(req.url).pathname.startsWith('/api/')) return;
  event.respondWith(fetch(req).then(response => {
    if (response.ok && ASSETS.includes(new URL(req.url).pathname)) {
      const clone = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(req, clone)));
    }
    return response;
  }).catch(() => caches.match(req)));
});
