// Service worker mínimo: cachea estáticos para carga rápida en el taller.
// No cachea respuestas dinámicas (órdenes) para evitar mostrar datos viejos.
const CACHE = 'vielma-static-v1';
const ASSETS = [
  '/static/css/styles.css',
  '/static/js/app.js',
  '/static/js/timer.js',
  '/static/js/reports.js',
  '/static/img/logo.svg',
  '/static/js/chart.umd.min.js'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method === 'GET' && url.pathname.startsWith('/static/')) {
    e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
  }
});
