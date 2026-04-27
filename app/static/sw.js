const CACHE_NAME = 'aproman-v2-cache-v2';

// Solo cacheamos assets estáticos que no cambian entre orígenes
const STATIC_ASSETS = [
  '/static/img/logo_procolor.png',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Solo interceptamos peticiones al mismo origen
  if (url.origin !== location.origin) return;

  // Solo cacheamos assets estáticos (rutas /static/ o /manifest.json)
  const isStaticAsset = url.pathname.startsWith('/static/') || url.pathname === '/manifest.json';

  if (!isStaticAsset || event.request.method !== 'GET') {
    // Para todo lo demás (rutas Flask, login, dashboards) ir directo a red sin interceptar
    return;
  }

  // El CSS principal siempre va a red para evitar diseños rotos por caché vieja.
  if (url.pathname === '/static/css/styles.css') {
    event.respondWith(fetch(event.request, { cache: 'no-store' }));
    return;
  }

  // Estrategia Cache-First solo para assets estáticos
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        // Solo guardar en caché si la respuesta es válida
        if (response && response.status === 200) {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
        }
        return response;
      });
    })
  );
});
