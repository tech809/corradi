// Editor único del perfil de compatibilidad. Lo usan el panel de la home ("Descubre qué
// encaja contigo"), el diálogo "Mi compatibilidad" de la home/fichas y el del mapa: antes
// había tres formularios distintos y el del mapa se había quedado en una versión antigua.
//
// Los cambios se guardan al momento en localStorage y se anuncian con el evento
// `corradi:profile-change` en window; cada página decide cómo recalcular al recibirlo.
(function (global) {
  "use strict";

  var C = global.CorradiCompatibility, K = global.Corradi;
  var TYPE_IDS = ["YOUTH_EXCHANGE", "TRAINING_COURSE", "VOLUNTEERING"];
  var PREF_LABEL = {avoid: "Evitar", positive: "Me interesa", required: "Muy importante"};
  var LIMITS = {required: 2, positive: 5};
  var MAX_WORDS = 3;

  function read() { return C.readProfile(); }
  function announce() { global.dispatchEvent(new CustomEvent("corradi:profile-change", {detail: read()})); }
  function save(patch) {
    var next = Object.assign({}, read(), patch);
    next.type = (next.types || []).length === 1 ? next.types[0] : "";
    try { localStorage.setItem(C.key, JSON.stringify(next)); } catch (e) {}
    announce();
  }
  function clear() {
    try { localStorage.removeItem(C.key); } catch (e) {}
    announce();
  }
  function words(p) { return String((p || read()).requiredText || "").split(",").map(function (w) { return w.trim(); }).filter(Boolean).slice(0, MAX_WORDS); }

  // "25 años · TC + YE · 2 temas · 1 palabra" (o "Sin completar").
  function summary(p) {
    p = p || read();
    var types = p.types || [], topics = Object.keys(p.priorities || {}).filter(function (k) { return p.priorities[k] !== "avoid"; }).length, w = words(p).length;
    if (!p.age && !types.length && !topics && !w) return "Sin completar";
    return [
      p.age ? p.age + " años" : "Sin edad",
      types.length ? types.map(K.typeShort).join(" + ") : "Todo",
      topics ? topics + (topics === 1 ? " tema" : " temas") : "",
      w ? w + (w === 1 ? " palabra" : " palabras") : ""
    ].filter(Boolean).join(" · ");
  }

  var HELP = 'El % dice qué parte de lo que buscas cubre cada oportunidad.<ul>' +
    '<li><b>+ Me interesa</b> cuenta 1; <b>++ Muy importante</b> y cada <b>palabra imprescindible</b> cuentan 2.</li>' +
    '<li>Cuenta entero si es el tema principal, un 60 % si sale en el título o los objetivos y un 25 % si solo se menciona de pasada.</li>' +
    '<li>Si falta algo muy importante o imprescindible, no pasa del 40 %. Cada tema a <b>evitar</b> que sea central resta 30.</li>' +
    '<li>Si la ficha tiene poca información, no pasa del 70 %.</li></ul>' +
    'El formato filtra, no suma. Y la afinidad nunca decide si puedes participar: eso solo lo decide tu edad.';

  function template() {
    var e = K.esc;
    return '' +
      '<div class="pe-field pe-age"><div class="pe-row"><label for="{id}Age">Tu edad</label><output data-pe="ageOut">—</output></div>' +
        '<input id="{id}Age" data-pe="age" type="range" min="13" max="40" step="1" value="22"><small>Desliza para ajustarla. Sin edad también filtra por temas.</small></div>' +
      '<fieldset class="pe-field"><legend>Qué buscas</legend><div class="pe-chips" data-pe="types">' +
        '<button type="button" class="pe-chip" data-type="" title="Todos los formatos">Todo</button>' +
        TYPE_IDS.map(function (t) { return '<button type="button" class="pe-chip" data-type="' + t + '" title="' + e(K.TYPES[t].label) + '">' + e(K.TYPES[t].short) + '</button>'; }).join("") +
      '</div></fieldset>' +
      '<div class="pe-field"><div class="pe-row"><label for="{id}Word">Palabras imprescindibles</label><span class="pe-count" data-pe="wordCount">0/3</span></div>' +
        '<div class="pe-tags" data-pe="tags"><input id="{id}Word" data-pe="word" maxlength="30" placeholder="Escribe y pulsa Enter" enterkeyhint="done" autocomplete="off"></div>' +
        '<small>Tienen que aparecer en la ficha. Si faltan, la afinidad no pasa del 40 %.</small></div>' +
      '<div class="pe-field"><div class="pe-row"><span class="pe-label">Temas</span><span class="pe-legend"><b>−</b> evitar · <b>+</b> me interesa · <b>++</b> muy importante</span></div>' +
        '<div class="pe-prefs" data-pe="prefs">' + C.taxonomy.map(function (c) {
          return '<div class="pe-pref" data-concept="' + c.id + '"><span class="pe-pref-name">' + e(c.label) + '</span><span class="pe-pref-state"></span><span class="pe-pref-btns">' +
            '<button type="button" data-mode="avoid" aria-label="Evitar ' + e(c.label) + '">−</button>' +
            '<button type="button" data-mode="positive" aria-label="Me interesa ' + e(c.label) + '">+</button>' +
            '<button type="button" data-mode="required" aria-label="Muy importante ' + e(c.label) + '">++</button></span></div>';
        }).join("") + '</div><small>Desliza dentro de la lista para ver los ' + C.taxonomy.length + ' temas.</small></div>' +
      '<p class="pe-msg" data-pe="msg" role="status" aria-live="polite"></p>' +
      '<details class="pe-help"><summary>¿Cómo se calcula el % de afinidad?</summary><div>' + HELP + '</div></details>' +
      '<div class="pe-foot"><small>Se guarda solo en este dispositivo.</small><button type="button" class="pe-reset" data-pe="reset">Borrar todo</button></div>';
  }

  var uid = 0;
  function mount(root, options) {
    options = options || {};
    var id = "pe" + (++uid);
    root.classList.add("pe", options.theme === "dark" ? "pe--dark" : "pe--light");
    root.innerHTML = template().replace(/\{id\}/g, id);
    var $ = function (name) { return root.querySelector('[data-pe="' + name + '"]'); };
    var msgTimer = null;
    function say(text) {
      var node = $("msg"); node.textContent = text; node.classList.add("show");
      clearTimeout(msgTimer); msgTimer = setTimeout(function () { node.classList.remove("show"); }, 2600);
    }

    var age = $("age");
    age.addEventListener("input", function () { save({age: age.value}); });

    $("types").addEventListener("click", function (event) {
      var chip = event.target.closest(".pe-chip"); if (!chip) return;
      var types = (read().types || []).slice(), t = chip.dataset.type;
      if (!t) types = [];
      else if (types.indexOf(t) >= 0) types = types.filter(function (x) { return x !== t; });
      else types.push(t);
      if (types.length === TYPE_IDS.length) types = [];
      save({types: types});
    });

    var word = $("word"), tags = $("tags");
    function addWord(keepFocus) {
      var value = word.value.replace(/,/g, " ").trim().slice(0, 30);
      word.value = "";
      if (!value) return;
      var list = words();
      if (list.some(function (w) { return w.toLowerCase() === value.toLowerCase(); })) return;
      if (list.length >= MAX_WORDS) { say("Máximo " + MAX_WORDS + " palabras imprescindibles."); return; }
      save({requiredText: list.concat(value).join(", ")});
      if (keepFocus) word.focus();
    }
    word.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === ",") { event.preventDefault(); addWord(true); }
      else if (event.key === "Backspace" && !word.value) { var list = words(); if (list.length) save({requiredText: list.slice(0, -1).join(", ")}); }
    });
    word.addEventListener("blur", function () { addWord(false); });
    tags.addEventListener("click", function (event) {
      var remove = event.target.closest("[data-remove-word]");
      if (remove) { save({requiredText: words().filter(function (w) { return w !== remove.dataset.removeWord; }).join(", ")}); return; }
      if (event.target === tags) word.focus();
    });

    var prefs = $("prefs");
    prefs.addEventListener("scroll", function () { prefs.classList.toggle("at-end", prefs.scrollTop + prefs.clientHeight >= prefs.scrollHeight - 4); }, {passive: true});
    prefs.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-mode]"); if (!button) return;
      var concept = button.closest(".pe-pref").dataset.concept, mode = button.dataset.mode;
      var priorities = Object.assign({}, read().priorities || {});
      if (priorities[concept] === mode) delete priorities[concept];
      else {
        if (LIMITS[mode] && Object.keys(priorities).filter(function (k) { return k !== concept && priorities[k] === mode; }).length >= LIMITS[mode]) {
          say(mode === "required" ? "Máximo 2 temas muy importantes." : "Máximo 5 temas en «me interesa».");
          return;
        }
        priorities[concept] = mode;
      }
      save({priorities: priorities});
    });

    $("reset").addEventListener("click", function () { clear(); say("Perfil borrado."); });

    function sync() {
      var p = read(), priorities = p.priorities || {}, types = p.types || [], list = words(p);
      if (document.activeElement !== age) age.value = p.age || 22;
      $("ageOut").textContent = p.age ? p.age + " años" : "Sin indicar";
      root.classList.toggle("pe-no-age", !p.age);
      Array.prototype.forEach.call(root.querySelectorAll(".pe-chip"), function (chip) {
        chip.setAttribute("aria-pressed", String(chip.dataset.type ? types.indexOf(chip.dataset.type) >= 0 : !types.length));
      });
      // Solo se repintan si cambian las palabras (si no, la animación de entrada se repetía
      // en cada movimiento del deslizador).
      var wordsKey = list.join("\u0000");
      if (tags.dataset.words !== wordsKey) {
        tags.dataset.words = wordsKey;
        Array.prototype.forEach.call(tags.querySelectorAll(".pe-tag"), function (tag) { tag.remove(); });
        word.insertAdjacentHTML("beforebegin", list.map(function (w) {
          return '<span class="pe-tag"><span aria-hidden="true">★</span>' + K.esc(w) + '<button type="button" data-remove-word="' + K.esc(w) + '" aria-label="Quitar ' + K.esc(w) + '">×</button></span>';
        }).join(""));
      }
      word.hidden = list.length >= MAX_WORDS;
      $("wordCount").textContent = list.length + "/" + MAX_WORDS;
      Array.prototype.forEach.call(prefs.querySelectorAll(".pe-pref"), function (row) {
        var state = priorities[row.dataset.concept] || "";
        row.dataset.state = state;
        row.querySelector(".pe-pref-state").textContent = PREF_LABEL[state] || "";
        Array.prototype.forEach.call(row.querySelectorAll("button[data-mode]"), function (b) { b.setAttribute("aria-pressed", String(b.dataset.mode === state)); });
      });
    }
    // Varios editores a la vez (panel + diálogo) se mantienen sincronizados entre sí.
    global.addEventListener("corradi:profile-change", sync);
    sync();
    return {sync: sync};
  }

  var dialog = null;
  function openDialog() {
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.className = "pe-dialog";
      dialog.setAttribute("aria-labelledby", "peDialogTitle");
      dialog.innerHTML = '<div class="pe-dialog-head"><div><span>Compatibilidad sin registro</span><h2 id="peDialogTitle">Mi compatibilidad</h2></div>' +
        '<button type="button" class="pe-dialog-close" aria-label="Cerrar">×</button></div><div class="pe-dialog-body"></div>' +
        '<div class="pe-dialog-foot"><span data-pe-summary></span><button type="button" class="pe-dialog-done">Listo</button></div>';
      document.body.appendChild(dialog);
      mount(dialog.querySelector(".pe-dialog-body"), {theme: "light"});
      var close = function () { dialog.close(); };
      dialog.querySelector(".pe-dialog-close").onclick = close;
      dialog.querySelector(".pe-dialog-done").onclick = close;
      dialog.addEventListener("click", function (event) { if (event.target === dialog) close(); });
      var paint = function () { dialog.querySelector("[data-pe-summary]").textContent = summary(); };
      global.addEventListener("corradi:profile-change", paint);
      paint();
    }
    if (!dialog.open) dialog.showModal();
  }

  // Cualquier elemento con data-open-profile abre el diálogo (tarjetas, avisos, menús).
  document.addEventListener("click", function (event) {
    var opener = event.target.closest && event.target.closest("[data-open-profile]");
    if (opener) { event.preventDefault(); openDialog(); }
  });

  global.CorradiProfileEditor = {mount: mount, openDialog: openDialog, summary: summary, words: words, save: save, clear: clear};
})(window);
