'use strict';

const SHELL_CACHE = 'artisan-market-offline-v2';
const OFFLINE_PAGE = '/offline/request-assistant/';
const PRECACHE_URLS = [
  OFFLINE_PAGE,
  '/static/css/site.css',
  '/static/css/conversations.css',
  '/static/css/offline-request-assistant.css',
  '/static/js/api-errors.js',
  '/static/js/site.js',
  '/static/js/pages/offline-request-assistant.js',
  '/static/fonts/DMSans-Latin-Variable.woff2',
  '/static/fonts/DMSerifDisplay-Regular.woff2',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys
        .filter((key) => key.startsWith('artisan-market-offline-') && key !== SHELL_CACHE)
        .map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function cachedOfflinePage() {
  return (await caches.match(OFFLINE_PAGE, { ignoreSearch: true }))
    || new Response('Offline draft workspace is not available yet. Reconnect once to install it.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
}

async function networkFirstPage(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok && new URL(request.url).pathname === OFFLINE_PAGE) {
      const cache = await caches.open(SHELL_CACHE);
      await cache.put(OFFLINE_PAGE, response.clone());
    }
    return response;
  } catch (_error) {
    return cachedOfflinePage();
  }
}

// Static assets are served from the cache for speed but always refreshed in the
// background. A shipped stylesheet or script can therefore never be pinned to an
// old copy by a long-lived browser cache.
async function staleWhileRevalidateAsset(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);
  return cached || (await network) || Response.error();
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname === OFFLINE_PAGE) {
    event.respondWith(networkFirstPage(request));
    return;
  }

  if (request.mode === 'navigate' && /^\/discover\/conversations\/[0-9a-f-]{36}\/?$/i.test(url.pathname)) {
    event.respondWith(fetch(request).catch(() => cachedOfflinePage()));
    return;
  }

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(staleWhileRevalidateAsset(request));
  }
});