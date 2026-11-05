/* Portada: secciones «Formatos» y «Destinos». Recibe el catálogo ya cargado por discover.html. */
(function () {
  "use strict";
  var TYPES = [
    { key: "YOUTH_EXCHANGE", label: "Youth Exchange", title: "Intercambio juvenil", img: "/assets/collection-youth-exchange-v2.jpg",
      text: "Grupos de jóvenes de varios países conviven y trabajan un tema con educación no formal.",
      facts: [["Edad", "13–30 años"], ["Duración", "5–21 días"], ["Ideal para", "Primera experiencia"]] },
    { key: "TRAINING_COURSE", label: "Training Course", title: "Curso de formación", img: "/assets/collection-training-course-v2.jpg",
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

  window.CorradiHomeExtras = function (all) {
    renderFormats(all || []);
    renderDestinations(all || []);
  };
})();
