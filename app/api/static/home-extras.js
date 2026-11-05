/* Portada: secciones «Formatos» y «Destinos». Recibe el catálogo ya cargado por discover.html. */
(function () {
  "use strict";
  var TYPES = [
    { key: "YOUTH_EXCHANGE", label: "Youth Exchange", title: "Intercambio juvenil", img: "/assets/proactive-ye.jpg",
      text: "Grupos de jóvenes de varios países conviven y trabajan un tema con educación no formal.",
      facts: [["Edad", "13–30 años"], ["Duración", "5–21 días"], ["Ideal para", "Primera experiencia"]] },
    { key: "TRAINING_COURSE", label: "Training Course", title: "Curso de formación", img: "/assets/proactive-tc.jpg",
      text: "Formación práctica para quienes trabajan con jóvenes: técnicos, monitores, voluntariado y docentes.",
      facts: [["Perfil", "Trabajo juvenil"], ["Duración", "De 2 días a 2 meses"], ["Ideal para", "Ganar competencias"]] },
    { key: "VOLUNTEERING", label: "Voluntariado ESC", title: "Voluntariado europeo", img: "/assets/pool/12.jpg",
      text: "Colabora con una entidad de otro país dentro del Cuerpo Europeo de Solidaridad.",
      facts: [["Edad", "18–30 años"], ["Duración", "De 2 semanas a 12 meses"], ["Ideal para", "Vivir fuera"]] }
  ];
  var names = null;
  try { names = new Intl.DisplayNames(["es"], { type: "region" }); } catch (e) { names = null; }
  function countryName(code) { try { return names ? names.of(code) : code; } catch (e) { return code; } }
  function flag(code) {
    return /^[A-Z]{2}$/.test(code) ? String.fromCodePoint.apply(null, code.split("").map(function (c) { return 127397 + c.charCodeAt(0); })) : "";
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (m) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]; }); }

  function renderFormats(all) {
    var box = document.getElementById("formatsGrid");
    if (!box) return;
    box.innerHTML = TYPES.map(function (t, i) {
      var n = all.filter(function (o) { return o.type === t.key; }).length;
      return '<a class="format-card" href="#explorar" data-format="' + t.key + '">' +
        '<div class="format-photo" style="background-image:url(\'' + t.img + '\')"></div>' +
        '<div class="format-body"><span class="format-index">0' + (i + 1) + " · " + t.label + "</span>" +
        "<h3>" + t.title + "</h3><p>" + t.text + "</p><dl>" +
        t.facts.map(function (f) { return "<dt>" + f[0] + "</dt><dd>" + f[1] + "</dd>"; }).join("") +
        '</dl><div class="format-foot"><span>Ver convocatorias →</span><b>' + n + "</b></div></div></a>";
    }).join("");
    box.addEventListener("click", function (e) {
      var card = e.target.closest("[data-format]");
      if (!card) return;
      var select = document.getElementById("type");
      if (select) { select.value = card.dataset.format; select.dispatchEvent(new Event("change", { bubbles: true })); }
    });
  }

  function renderDestinations(all) {
    var box = document.getElementById("destGrid");
    if (!box) return;
    var counts = {};
    all.forEach(function (o) { if (o.country_code) counts[o.country_code] = (counts[o.country_code] || 0) + 1; });
    var top = Object.keys(counts).map(function (k) { return [k, counts[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; }).slice(0, 12);
    var max = top.length ? top[0][1] : 1;
    box.innerHTML = top.map(function (c) {
      return '<a class="dest-card" href="/mapa?country=' + encodeURIComponent(c[0]) + '">' +
        '<span class="dest-flag" aria-hidden="true">' + flag(c[0]) + "</span><b>" + esc(countryName(c[0])) + "</b>" +
        "<span>" + c[1] + " convocatoria" + (c[1] === 1 ? "" : "s") + "</span>" +
        '<i class="dest-bar"><i style="width:' + Math.max(6, Math.round(c[1] / max * 100)) + '%"></i></i></a>';
    }).join("");
  }

  function renderChannels() {
    var box = document.getElementById("channelsGrid");
    var C = window.CORRADI_CHANNELS;
    if (!box || !C) return;
    var cta = { wa: "Unirme al canal", tg: "Unirme al canal", ig: "Seguir", bot: "Abrir el bot" };
    box.innerHTML = C.list.map(function (c) {
      return '<a class="channel-card ' + c.k + '" href="' + c.url + '" target="_blank" rel="noopener">' +
        '<span class="sn-ico ' + c.k + '">' + C.icon[c.k] + "</span><span><b>" + esc(c.name) + '</b><span class="hint">' + esc(c.hint) + "</span></span>" +
        '<span class="go">' + cta[c.k] + " <i>→</i></span></a>";
    }).join("");
  }

  function countUp(el, to) {
    if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = to.toLocaleString("es-ES"); return; }
    el.textContent = "0";
    var io = new IntersectionObserver(function (es) {
      if (!es[0].isIntersecting) return;
      io.disconnect();
      var t0 = performance.now(), d = 1400;
      (function tick(t) {
        var k = Math.min(1, (t - t0) / d), e = 1 - Math.pow(1 - k, 3);
        el.textContent = Math.round(to * e).toLocaleString("es-ES");
        if (k < 1) requestAnimationFrame(tick);
      })(t0);
    }, { threshold: .4 });
    io.observe(el);
  }

  function renderTrust(all) {
    var box = document.getElementById("trust");
    if (!box || !all.length) return;
    var uniq = function (f) { var s = {}; all.forEach(function (o) { var v = f(o); if (v) s[v] = 1; }); return Object.keys(s).length; };
    var vals = { open: all.length, countries: uniq(function (o) { return o.country_code; }), orgs: uniq(function (o) { return (o.organiser_name || "").trim().toLowerCase(); }) };
    box.querySelectorAll("[data-trust]").forEach(function (el) { countUp(el, vals[el.dataset.trust] || 0); });
    var last = all.reduce(function (m, o) { var t = Date.parse(o.source_checked_at || o.updated || ""); return t > m ? t : m; }, 0);
    var live = document.getElementById("trustLive");
    if (live && last) {
      var min = Math.max(1, Math.round((Date.now() - last) / 60000));
      live.textContent = "Comprobado hace " + (min < 60 ? min + " min" : min < 1440 ? Math.round(min / 60) + " h" : Math.round(min / 1440) + " d");
    }
  }

  window.CorradiHomeExtras = function (all) {
    renderFormats(all || []);
    renderDestinations(all || []);
    renderTrust(all || []);
  };
  renderChannels();
})();
