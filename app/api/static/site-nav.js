/* Menú superior único de Corradi. Cada página pone <div id="site-nav"></div> donde iba su
   cabecera y carga este script; así el menú es idéntico en todas y se cambia en un solo
   sitio. Los canales también se exponen en window.CORRADI_CHANNELS para la portada. */
(function () {
  var ICON = {
    wa: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.3-.4.8-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.8 11.9 11.9 0 0 0 4.6 4c1.7.7 2.4.8 3.2.7.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.2-.2-.5-.3Z"/></svg>',
    tg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.9 4.3 18.8 19c-.2 1-.8 1.3-1.7.8l-4.6-3.4-2.2 2.1c-.3.3-.5.5-1 .5l.3-4.7 8.6-7.8c.4-.3-.1-.5-.6-.2L6.9 13 2.3 11.6c-1-.3-1-1 .2-1.5l18-6.9c.8-.3 1.6.2 1.4 1.1Z"/></svg>',
    ig: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>',
    bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
    map: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9 4-6 2.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4Z"/><path d="M9 4v13M15 6.5v13"/></svg>',
    caret: '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.6"><path d="m2 3.5 3 3 3-3"/></svg>',
    burger: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>'
  };
  var CHANNELS = [
    { k: "wa", name: "Canal de WhatsApp", hint: "Cada oportunidad nueva, en tu móvil", url: "https://whatsapp.com/channel/0029Vb3ToJoLCoXAGbQ6ll1W" },
    { k: "tg", name: "Canal de Telegram", hint: "Lo mismo, al instante, en Telegram", url: "https://t.me/erasmuscorradi" },
    { k: "ig", name: "Instagram", hint: "@corradierasmus · las mejores, cada día", url: "https://www.instagram.com/corradierasmus/" },
    { k: "bot", name: "Envía una oportunidad", hint: "Reenvíala a nuestro bot de Telegram", url: "https://t.me/corradi_erasmus_bot" }
  ];
  window.CORRADI_CHANNELS = { list: CHANNELS, icon: ICON };

  var LINKS = [
    { href: "/", label: "Oportunidades" },
    { href: "/mapa", label: "Mapa" },
    { href: "/guia", label: "Guía" },
    { href: "/organizaciones", label: "Organizaciones", md: true }
  ];
  var MORE = [
    { href: "/quienes-somos", label: "Quiénes somos", hint: "El proyecto y quién está detrás" },
    { href: "/estadisticas", label: "Estadísticas", hint: "Datos abiertos del catálogo" },
    { href: "/organizaciones", label: "Organizaciones", hint: "Entidades de envío en España" },
    { href: "/?profile=1", label: "Mi compatibilidad", hint: "Tu perfil y tus guardadas" }
  ];
  var path = location.pathname.replace(/\/+$/, "") || "/";
  function cur(h) { return h === path || (h === "/mapa" && path === "/corradi-erasmus") ? ' aria-current="page"' : ""; }
  function ext(u) { return /^https?:/.test(u) ? ' target="_blank" rel="noopener"' : ""; }
  function chan(c) {
    return '<a href="' + c.url + '"' + ext(c.url) + '><span class="sn-ico ' + c.k + '">' + ICON[c.k] + '</span><span>' + c.name + '<small>' + c.hint + "</small></span></a>";
  }
  var brand = '<a class="sn-brand" href="/" aria-label="Corradi, inicio"><span class="sn-mk"><img src="/assets/logo-mark.svg" alt=""></span><span><b>Corradi</b><small>ERASMUS+ EN CLARO</small></span></a>';

  var html =
    '<header class="sn" role="banner"><div class="sn-in">' + brand +
    '<nav class="sn-links" aria-label="Principal">' +
    LINKS.map(function (l) { return '<a href="' + l.href + '"' + (l.md ? ' class="sn-hide-md"' : "") + cur(l.href) + ">" + l.label + "</a>"; }).join("") +
    '<div class="sn-drop' + (MORE.some(function (m) { return m.href === path; }) ? " sn-cur" : "") + '"><button type="button" aria-expanded="false">Más ' + ICON.caret + '</button><div class="sn-panel">' +
    MORE.map(function (m) { return '<a href="' + m.href + '"' + cur(m.href) + "><span>" + m.label + "<small>" + m.hint + "</small></span></a>"; }).join("") +
    "</div></div>" +
    '<div class="sn-drop"><button type="button" aria-expanded="false">Avisos ' + ICON.caret + '</button><div class="sn-panel">' +
    CHANNELS.map(chan).join("") + "</div></div>" +
    "</nav>" +
    '<div class="sn-acts"><a class="sn-btn line" href="/publicar">Publicar</a><a class="sn-btn clay" href="/mapa">' + ICON.map + "<span>Abrir mapa</span></a>" +
    '<button class="sn-burger" type="button" aria-label="Abrir menú" aria-expanded="false">' + ICON.burger + "</button></div>" +
    "</div></header>" +
    '<div class="sn-sheet" aria-hidden="true"><div class="sn-sheet-in" role="dialog" aria-label="Menú">' +
    '<div class="sn-sheet-head">' + brand.replace("sn-brand", "sn-brand sn-brand-sheet") + '<button class="sn-burger" style="display:grid" type="button" aria-label="Cerrar menú" data-sn-close>' + ICON.close + "</button></div>" +
    "<nav><h6>Explora</h6>" +
    LINKS.concat([{ href: "/quienes-somos", label: "Quiénes somos" }, { href: "/estadisticas", label: "Estadísticas" }, { href: "/?profile=1", label: "Mi compatibilidad" }, { href: "/publicar", label: "Publicar una oportunidad" }])
      .map(function (l) { return '<a href="' + l.href + '"' + cur(l.href) + ">" + l.label + "</a>"; }).join("") +
    "<h6>Entérate de todo</h6>" + CHANNELS.map(chan).join("") + "</nav></div></div>";

  function mount() {
    var slot = document.getElementById("site-nav");
    if (!slot) { slot = document.createElement("div"); document.body.insertBefore(slot, document.body.firstChild); }
    slot.outerHTML = html;
    var drops = document.querySelectorAll(".sn-drop");
    drops.forEach(function (d) {
      var b = d.querySelector("button");
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        var open = !d.classList.contains("open");
        drops.forEach(function (o) { o.classList.remove("open"); o.querySelector("button").setAttribute("aria-expanded", "false"); });
        if (open) { d.classList.add("open"); b.setAttribute("aria-expanded", "true"); }
      });
    });
    document.addEventListener("click", function (e) { if (!e.target.closest(".sn-drop")) drops.forEach(function (o) { o.classList.remove("open"); }); });
    var sheet = document.querySelector(".sn-sheet");
    function setSheet(on) { sheet.classList.toggle("open", on); sheet.setAttribute("aria-hidden", on ? "false" : "true"); document.documentElement.style.overflow = on ? "hidden" : ""; }
    document.querySelector(".sn .sn-burger").addEventListener("click", function () { setSheet(true); });
    sheet.addEventListener("click", function (e) { if (e.target === sheet || e.target.closest("[data-sn-close]")) setSheet(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { setSheet(false); drops.forEach(function (o) { o.classList.remove("open"); }); } });
  }

  // ---- Pie de página común ----
  var FOOT_COLS = [
    { h: "Explora", l: [["/", "Oportunidades"], ["/mapa", "Mapa"], ["/?profile=1", "Mi compatibilidad"]] },
    { h: "Aprende", l: [["/guia", "Guía Erasmus+"], ["/organizaciones", "Organizaciones"], ["/estadisticas", "Estadísticas"]] },
    { h: "Corradi", l: [["/quienes-somos", "Quiénes somos"], ["/publicar", "Publicar una oportunidad"], ["mailto:general@proactivefuture.eu", "Contacto"]] }
  ];
  var EU = '<svg class="sf-eu" viewBox="0 0 60 40" aria-hidden="true"><rect width="60" height="40" fill="#039"/><g fill="#fc0"><polygon points="50.00,16.70 50.74,18.98 53.14,18.98 51.20,20.39 51.94,22.67 50.00,21.26 48.06,22.67 48.80,20.39 46.86,18.98 49.26,18.98"/><polygon points="47.32,26.70 48.06,28.98 50.46,28.98 48.52,30.39 49.26,32.67 47.32,31.26 45.38,32.67 46.12,30.39 44.18,28.98 46.58,28.98"/><polygon points="40.00,34.02 40.74,36.30 43.14,36.30 41.20,37.71 41.94,39.99 40.00,38.58 38.06,39.99 38.80,37.71 36.86,36.30 39.26,36.30"/><polygon points="30.00,36.70 30.74,38.98 33.14,38.98 31.20,40.39 31.94,42.67 30.00,41.26 28.06,42.67 28.80,40.39 26.86,38.98 29.26,38.98"/><polygon points="20.00,34.02 20.74,36.30 23.14,36.30 21.20,37.71 21.94,39.99 20.00,38.58 18.06,39.99 18.80,37.71 16.86,36.30 19.26,36.30"/><polygon points="12.68,26.70 13.42,28.98 15.82,28.98 13.88,30.39 14.62,32.67 12.68,31.26 10.74,32.67 11.48,30.39 9.54,28.98 11.94,28.98"/><polygon points="10.00,16.70 10.74,18.98 13.14,18.98 11.20,20.39 11.94,22.67 10.00,21.26 8.06,22.67 8.80,20.39 6.86,18.98 9.26,18.98"/><polygon points="12.68,6.70 13.42,8.98 15.82,8.98 13.88,10.39 14.62,12.67 12.68,11.26 10.74,12.67 11.48,10.39 9.54,8.98 11.94,8.98"/><polygon points="20.00,-0.62 20.74,1.66 23.14,1.66 21.20,3.07 21.94,5.35 20.00,3.94 18.06,5.35 18.80,3.07 16.86,1.66 19.26,1.66"/><polygon points="30.00,-3.30 30.74,-1.02 33.14,-1.02 31.20,0.39 31.94,2.67 30.00,1.26 28.06,2.67 28.80,0.39 26.86,-1.02 29.26,-1.02"/><polygon points="40.00,-0.62 40.74,1.66 43.14,1.66 41.20,3.07 41.94,5.35 40.00,3.94 38.06,5.35 38.80,3.07 36.86,1.66 39.26,1.66"/><polygon points="47.32,6.70 48.06,8.98 50.46,8.98 48.52,10.39 49.26,12.67 47.32,11.26 45.38,12.67 46.12,10.39 44.18,8.98 46.58,8.98"/></g></svg>';
  var footHtml =
    '<footer class="sf" role="contentinfo"><div class="sf-in">' +
    '<div class="sf-top"><p class="sf-claim">Que nadie se quede sin su Erasmus+ <em>por no enterarse a tiempo.</em></p>' +
    '<div class="sf-chan">' + CHANNELS.map(function (c) { return '<a href="' + c.url + '" target="_blank" rel="noopener" aria-label="' + c.name + '"><span class="sn-ico ' + c.k + '">' + ICON[c.k] + "</span><span>" + c.name.replace("Canal de ", "") + "</span></a>"; }).join("") + "</div></div>" +
    '<div class="sf-grid"><div class="sf-brand"><a class="sn-brand" href="/" aria-label="Corradi, inicio"><span class="sn-mk"><img src="/assets/logo-mark.svg" alt=""></span><span><b>Corradi</b><small>ERASMUS+ EN CLARO</small></span></a>' +
    "<p>Todas las convocatorias abiertas de intercambios, cursos y voluntariado europeo, con su fuente original y verificadas a diario. Un proyecto de Proactive Future.</p></div>" +
    FOOT_COLS.map(function (c) { return "<nav><h5>" + c.h + "</h5>" + c.l.map(function (a) { return '<a href="' + a[0] + '">' + a[1] + "</a>"; }).join("") + "</nav>"; }).join("") + "</div>" +
    '<div class="sf-eu-row">' + EU + "<div><b>Cofinanciado por la Unión Europea</b><p>Las opiniones y puntos de vista expresados solo comprometen a su(s) autor(es) y no reflejan necesariamente los de la Unión Europea ni los de la autoridad otorgante. Ni la Unión Europea ni la autoridad otorgante pueden ser consideradas responsables de ellos.</p></div></div>" +
    '<div class="sf-legal"><span>© ' + new Date().getFullYear() + " Corradi · Proactive Future</span><span>Hecho en España para toda Europa</span></div>" +
    "</div></footer>";
  function mountFooter() {
    var slot = document.getElementById("site-footer");
    if (slot) slot.outerHTML = footHtml;
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountFooter); else mountFooter();
  // Cargado justo después de su hueco (sin defer): se pinta ya, sin salto de maquetación.
  if (document.getElementById("site-nav") || document.readyState !== "loading") mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();
