/* Portada: secciones «Formatos» y «Destinos». Recibe el catálogo ya cargado por discover.html. */
(function () {
  "use strict";
  var TYPES = [
    { key: "YOUTH_EXCHANGE", label: "Youth Exchange", title: "Intercambio juvenil", img: "/assets/photo-ye.jpg",
      text: "Grupos de jóvenes de varios países conviven y trabajan un tema con educación no formal.",
      facts: [["Edad", "13–30 años"], ["Duración", "5–21 días"], ["Ideal para", "Primera experiencia"]] },
    { key: "TRAINING_COURSE", label: "Training Course", title: "Curso de formación", img: "/assets/photo-tc.jpg",
      text: "Formación práctica para quienes trabajan con jóvenes: técnicos, monitores, voluntariado y docentes.",
      facts: [["Perfil", "Trabajo juvenil"], ["Duración", "De 2 días a 2 meses"], ["Ideal para", "Ganar competencias"]] },
    { key: "VOLUNTEERING", label: "Voluntariado ESC", title: "Voluntariado europeo", img: "/assets/photo-esc.jpg",
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


  // ---- Calendario de plazos (YE + TC; ESC solo si se marca, porque son muchísimos) ----
  var MONTHS = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
  var TYPE_SHORT = { YOUTH_EXCHANGE: "YE", TRAINING_COURSE: "TC", VOLUNTEERING: "ESC", ESC: "ESC" };
  function ymd(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function renderCalendar(all) {
    var grid = document.getElementById("calGrid");
    if (!grid) return;
    var esc = document.getElementById("calEsc"), today = new Date(); today.setHours(0, 0, 0, 0);
    var tkey = ymd(today), view = new Date(today.getFullYear(), today.getMonth(), 1), picked = null;
    function items() {
      return all.filter(function (o) {
        var isEsc = o.type === "VOLUNTEERING" || o.type === "ESC";
        return o.application_deadline && o.application_deadline >= tkey && (!isEsc || esc.checked);
      });
    }
    function byDay(list) { var m = {}; list.forEach(function (o) { (m[o.application_deadline] = m[o.application_deadline] || []).push(o); }); return m; }
    function row(o) {
      var t = TYPE_SHORT[o.type] || "";
      return '<a class="cal-item" href="/proyecto/' + encodeURIComponent(o.identifier) + '"><span class="cal-t t-' + t.toLowerCase() + '">' + t + "</span>" +
        "<span><b>" + esc_(o.title) + "</b><small>" + esc_([o.location, countryName(o.country_code)].filter(Boolean).join(" · ")) +
        (o.deadline_estimated ? " · plazo aproximado" : "") + "</small></span>" + (o.last_minute ? '<i class="lastcall-tag">Last call</i>' : "") + "</a>";
    }
    function fmtDay(k) { var d = new Date(k + "T00:00:00"); return d.getDate() + " de " + MONTHS[d.getMonth()]; }
    function draw() {
      var list = items(), map = byDay(list);
      document.getElementById("calLabel").textContent = MONTHS[view.getMonth()].replace(/^./, function (c) { return c.toUpperCase(); }) + " " + view.getFullYear();
      var first = (view.getDay() + 6) % 7, days = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate(), html = "";
      ["L","M","X","J","V","S","D"].forEach(function (d) { html += '<span class="cal-dow">' + d + "</span>"; });
      for (var i = 0; i < first; i++) html += "<span></span>";
      for (var d = 1; d <= days; d++) {
        var k = ymd(new Date(view.getFullYear(), view.getMonth(), d)), n = (map[k] || []).length, past = k < tkey;
        html += '<button type="button" class="cal-day' + (n ? " has" : "") + (past ? " past" : "") + (k === tkey ? " today" : "") + (k === picked ? " picked" : "") +
          '" data-day="' + k + '"' + (n ? "" : " disabled") + ' aria-label="' + d + " " + MONTHS[view.getMonth()] + (n ? ", " + n + " cierran" : "") + '"><span>' + d + "</span>" + (n ? "<i>" + n + "</i>" : "") + "</button>";
      }
      grid.innerHTML = html;
      var box = document.getElementById("calList"), title = document.getElementById("calListTitle");
      if (picked && map[picked]) {
        title.textContent = "Cierran el " + fmtDay(picked);
        box.innerHTML = map[picked].map(row).join("") + '<button type="button" class="cal-reset">← Ver todos los próximos cierres</button>';
      } else {
        title.textContent = "Próximos cierres";
        var keys = Object.keys(map).sort().slice(0, 6);
        box.innerHTML = keys.length ? keys.map(function (k) { return '<div class="cal-group"><h4>' + fmtDay(k) + "</h4>" + map[k].map(row).join("") + "</div>"; }).join("") : '<p class="cal-empty">No hay plazos próximos con estos filtros.</p>';
      }
    }
    grid.addEventListener("click", function (e) { var b = e.target.closest("[data-day]"); if (!b || b.disabled) return; picked = picked === b.dataset.day ? null : b.dataset.day; draw(); });
    document.getElementById("calList").addEventListener("click", function (e) { if (e.target.closest(".cal-reset")) { picked = null; draw(); } });
    document.getElementById("calPrev").onclick = function () { if (view <= new Date(today.getFullYear(), today.getMonth(), 1)) return; view = new Date(view.getFullYear(), view.getMonth() - 1, 1); draw(); };
    document.getElementById("calNext").onclick = function () { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); draw(); };
    esc.onchange = function () { picked = null; draw(); };
    draw();
  }
  function esc_(s) { return esc(s); }
  window.CorradiHomeExtras = function (all) {
    renderFormats(all || []);
    renderDestinations(all || []);
    renderTrust(all || []);
    renderCalendar(all || []);
  };
  renderChannels();
})();
