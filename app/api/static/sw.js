const CACHE = "corradi-shell-v4";
const SHELL = [
  "/", "/mapa", "/organizaciones", "/guia", "/manifest.webmanifest",
  "/assets/discover-product.css", "/assets/discover-product.js", "/assets/compatibility.js",
  "/assets/icon-192.png", "/assets/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== location.origin) return;
  const url = new URL(request.url);
  const isDocument = request.mode === "navigate";
  const isData = url.pathname.startsWith("/api/") || url.pathname.startsWith("/opportunities/");
  if (isDocument || isData) {
    event.respondWith(fetch(request).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
      return response;
    }).catch(async () => (await caches.match(request)) || (isDocument ? caches.match("/") : new Response(JSON.stringify({count:0,results:[],offline:true}), {headers:{"Content-Type":"application/json"}}))));
    return;
  }
  event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
    if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
    return response;
  })));
});
