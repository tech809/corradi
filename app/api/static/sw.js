const CACHE = "corradi-shell-v27";
// Imágenes en una caché aparte y con tope: sin límite, cada foto vista (fichas, /media,
// tarjetas de compartir) se quedaba para siempre en el dispositivo.
const IMG_CACHE = "corradi-img-v1";
const IMG_MAX_ENTRIES = 120;
const SHELL = [
  "/", "/mapa", "/organizaciones", "/guia", "/manifest.webmanifest",
  "/assets/discover-product.css", "/assets/discover-product.js", "/assets/compatibility.js",
  "/assets/corradi-core.js", "/assets/profile-editor.js", "/assets/profile-editor.css",
  "/assets/icon-192.png", "/assets/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE && key !== IMG_CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== location.origin) return;
  const url = new URL(request.url);
  const isDocument = request.mode === "navigate";
  const isData = url.pathname.startsWith("/api/") || url.pathname.startsWith("/opportunities/");
  // JS y CSS también van primero a la red: si salieran de caché mientras el HTML llega nuevo,
  // tras cada deploy se mezclaban versiones (HTML nuevo con JS/CSS viejos = sección rota).
  // El servidor responde 304 si no cambiaron, así que apenas cuesta; la caché queda para offline.
  const isCode = /\.(js|css)$/.test(url.pathname) && url.pathname !== "/sw.js";
  if (isDocument || isData || isCode) {
    event.respondWith(fetch(request).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
      return response;
    }).catch(async () => (await caches.match(request)) || (isDocument ? caches.match("/") : new Response(JSON.stringify({count:0,results:[],offline:true}), {headers:{"Content-Type":"application/json"}}))));
    return;
  }
  const isImage = request.destination === "image" || /\.(jpe?g|png|webp|gif|svg)$/i.test(url.pathname);
  const runtimeCache = isImage ? IMG_CACHE : CACHE;
  event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(runtimeCache).then(cache => cache.put(request, copy)).then(() => isImage && trimCache(IMG_CACHE, IMG_MAX_ENTRIES)));
    }
    return response;
  })));
});

// Borra las entradas más antiguas (cache.keys() devuelve orden de inserción) hasta el tope.
async function trimCache(name, max) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - max)).map(key => cache.delete(key)));
}
