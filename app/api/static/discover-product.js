(function () {
  "use strict";

  const KEYS = {
    profile: "corradi-profile-v3",
    applications: "corradi-applications-v1",
    compare: "corradi-compare-v1",
    documents: "corradi-documents-v1",
    snapshots: "corradi-opportunity-snapshots-v1",
    changes: "corradi-opportunity-changes-v1",
  };
  const TYPES = {YOUTH_EXCHANGE: "Youth Exchange", TRAINING_COURSE: "Training Course", VOLUNTEERING: "ESC", ESC: "ESC"};
  const COUNTRIES = {ES:"España",IT:"Italia",RO:"Rumanía",GR:"Grecia",PL:"Polonia",DE:"Alemania",PT:"Portugal",FR:"Francia",HR:"Croacia",BG:"Bulgaria",HU:"Hungría",LT:"Lituania",LV:"Letonia",SK:"Eslovaquia",SI:"Eslovenia",EE:"Estonia",NL:"Países Bajos",BE:"Bélgica",CZ:"Chequia",AT:"Austria",SE:"Suecia",FI:"Finlandia",DK:"Dinamarca",MT:"Malta",IE:"Irlanda",CY:"Chipre",TR:"Turquía",MK:"Macedonia del Norte",RS:"Serbia",BA:"Bosnia y Herzegovina",AL:"Albania",ME:"Montenegro",GE:"Georgia",NO:"Noruega",IS:"Islandia",UA:"Ucrania",GB:"Reino Unido"};
  const STATUS = {saved:"Guardada",preparing:"Preparando",sent:"Enviada",interview:"Entrevista",accepted:"Aceptada",rejected:"No seleccionada"};
  const ORIGINS = {madrid:[40.4168,-3.7038],barcelona:[41.3874,2.1686],valencia:[39.4699,-0.3763],sevilla:[37.3891,-5.9845],bilbao:[43.263,-2.935]};
  const DEFAULT_DOCS = ["Documento de identidad en vigor", "Formulario de solicitud", "Carta o respuestas de motivación", "Confirmación de selección", "Billetes y justificantes de pago", "Tarjeta sanitaria o seguro", "Datos bancarios para el reembolso"];

  let catalog = [];
  let generated = "";
  let currentProject = null;
  let toastTimer = null;

  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch (_) { return fallback; }
  }
  function write(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
  function esc(value) { const node = document.createElement("div"); node.textContent = value == null ? "" : String(value); return node.innerHTML; }
  function fmt(value) { return value ? new Intl.DateTimeFormat("es", {day:"numeric", month:"short", year:"numeric"}).format(new Date(value + "T12:00:00")) : "Por confirmar"; }
  function projectUrl(project) { return "/proyecto/" + encodeURIComponent(project.identifier); }
  function byId(identifier) { return catalog.find(project => project.identifier === identifier); }
  function profile() { return window.CorradiCompatibility ? window.CorradiCompatibility.readProfile() : read(KEYS.profile, {}); }
  function applications() { return read(KEYS.applications, {}); }
  function compareIds() { return read(KEYS.compare, []); }
  function documents() { return read(KEYS.documents, {}); }
  function beacon(identifier, kind) {
    if (!identifier) return;
    const body = JSON.stringify({identifier, kind});
    if (navigator.sendBeacon) navigator.sendBeacon("/api/interaction", new Blob([body], {type:"application/json"}));
    else fetch("/api/interaction", {method:"POST", headers:{"Content-Type":"application/json"}, body, keepalive:true}).catch(() => {});
  }
  function toast(message) {
    let node = document.querySelector(".toast");
    if (!node) { node = document.createElement("div"); node.className = "toast"; node.setAttribute("role", "status"); document.body.appendChild(node); }
    node.textContent = message; node.classList.add("show"); clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("show"), 2400);
  }

  function eligibility(project, data) {
    return window.CorradiCompatibility.evaluate(project, data || profile());
  }

  const SNAPSHOT_FIELDS = {application_deadline:"Fecha límite",start_date:"Fecha de inicio",end_date:"Fecha final",application_url:"Formulario",infopack_url:"Infopack",participant_min_age:"Edad mínima",participant_max_age:"Edad máxima",eligibility_country_codes:"Países admitidos",status:"Disponibilidad"};
  function snapshot(project) {
    const out = {title:project.title || project.identifier};
    Object.keys(SNAPSHOT_FIELDS).forEach(key => { const value = project[key]; out[key] = Array.isArray(value) ? value.slice().sort().join(",") : (value == null ? "" : String(value)); });
    return out;
  }
  function trackedIds() {
    const favourites = read("corradi-favourites", []);
    return new Set([...Object.keys(applications()), ...compareIds(), ...favourites]);
  }
  function detectChanges() {
    const previous = read(KEYS.snapshots, {}), next = {}, tracked = trackedIds(), changes = read(KEYS.changes, {});
    catalog.forEach(project => {
      const current = snapshot(project), before = previous[project.identifier]; next[project.identifier] = current;
      if (!before || !tracked.has(project.identifier)) return;
      const labels = Object.keys(SNAPSHOT_FIELDS).filter(key => String(before[key] || "") !== String(current[key] || "")).map(key => SNAPSHOT_FIELDS[key]);
      if (labels.length) changes[project.identifier] = {title:current.title, labels, detectedAt:new Date().toISOString(), seen:false};
    });
    tracked.forEach(id => {
      if (previous[id] && !next[id]) {
        next[id] = previous[id];
        if (!changes[id] || !changes[id].labels.includes("Ya no aparece entre las oportunidades abiertas")) {
          changes[id] = {title:previous[id].title || id, labels:["Ya no aparece entre las oportunidades abiertas"], detectedAt:new Date().toISOString(), seen:false};
        }
      }
    });
    write(KEYS.snapshots, next); write(KEYS.changes, changes); updateChangeCount();
  }
  function updateChangeCount() {
    const count = Object.values(read(KEYS.changes, {})).filter(change => !change.seen).length;
    const node = document.getElementById("mobileChangeCount"); if (node) { node.textContent = count; node.hidden = !count; }
    const summary = document.getElementById("applicationSummary");
    if (summary && count) summary.textContent = count + (count === 1 ? " cambio detectado" : " cambios detectados");
  }

  function updateSummaries() {
    const p = profile(), apps = applications(), compare = compareIds();
    const pNode = document.getElementById("profileSummary");
    if (pNode) pNode.textContent = (p.age || p.type || Object.keys(p.priorities || {}).length) ? "Guardado en este dispositivo" : "Comprueba requisitos sin registrarte";
    const aNode = document.getElementById("applicationSummary");
    if (aNode) aNode.textContent = Object.keys(apps).length ? Object.keys(apps).length + " en seguimiento" : "Organiza tu progreso";
    const cNode = document.getElementById("compareSummary");
    if (cNode) cNode.textContent = compare.length + (compare.length === 1 ? " seleccionada" : " seleccionadas");
    updateChangeCount();
    renderTopMatches();
  }

  const QUICK_TOPICS = ["outdoor","sport","sustainability","wellbeing","creative","intercultural","inclusion","digital","leadership","rights"];
  const TYPE_SHORT = {YOUTH_EXCHANGE:"Youth Exchange", TRAINING_COURSE:"Training Course", VOLUNTEERING:"ESC", ESC:"ESC"};
  function daysLeft(project) {
    if (!project.application_deadline) return null;
    return Math.ceil((new Date(project.application_deadline + "T23:59:59") - new Date()) / 86400000);
  }
  function deadlineLabel(days) {
    if (days == null) return "Sin fecha límite";
    if (days <= 0) return "Cierra hoy";
    if (days === 1) return "Cierra mañana";
    return "Cierra en " + days + " días";
  }
  function flag(code) {
    return code && /^[A-Z]{2}$/i.test(code) ? String.fromCodePoint.apply(null, code.toUpperCase().split("").map(ch => 127397 + ch.charCodeAt(0))) : "";
  }
  function imageFor(project) {
    return project.image_url || (window.CorradiImageFor ? window.CorradiImageFor(project) : "");
  }
  let saveTimer = null;
  function saveQuick(patch, immediate) {
    write(KEYS.profile, Object.assign({}, profile(), patch));
    renderTopMatches();
    clearTimeout(saveTimer);
    // Sincronizar el catálogo de abajo es caro (re-render entero): lo diferimos mientras se arrastra.
    saveTimer = setTimeout(() => {
      const p = profile(), age = document.getElementById("age");
      if (age && age.value !== String(p.age || "")) { age.value = p.age || ""; age.dispatchEvent(new Event("input", {bubbles:true})); }
      updateSummaries(); enhanceCards();
    }, immediate ? 0 : 350);
  }
  const PREF_LABEL = {avoid:"Evitar", positive:"Me interesa", required:"Muy importante"};
  function requiredWords(p) { return String((p || profile()).requiredText || "").split(",").map(w => w.trim()).filter(Boolean).slice(0, 3); }
  function setupQuickProfile() {
    const form = document.getElementById("quickProfile");
    if (!form || form.dataset.ready) return;
    form.dataset.ready = "1";
    const ageInput = form.querySelector("#qpAge");
    ageInput.addEventListener("input", () => saveQuick({age: ageInput.value}));
    const typeHolder = form.querySelector("#qpType");
    typeHolder.innerHTML = [["", "Todo"], ["YOUTH_EXCHANGE", "Youth Exchange"], ["TRAINING_COURSE", "Training Course"], ["VOLUNTEERING", "Voluntariado ESC"]]
      .map(([value, label]) => '<button type="button" class="qp-chip" data-type="' + value + '">' + label + '</button>').join("");
    typeHolder.addEventListener("click", event => {
      const chip = event.target.closest(".qp-chip"); if (chip) saveQuick({type: chip.dataset.type}, true);
    });

    // Palabras imprescindibles: cada palabra se convierte en etiqueta al pulsar Enter o coma.
    const wordInput = form.querySelector("#qpWordInput"), tags = form.querySelector("#qpTags");
    const addWord = () => {
      const word = wordInput.value.replace(/,/g, " ").trim().slice(0, 30);
      wordInput.value = "";
      if (!word) return;
      const words = requiredWords();
      if (words.some(w => w.toLowerCase() === word.toLowerCase())) return;
      if (words.length >= 3) { toast("Máximo 3 palabras imprescindibles"); return; }
      saveQuick({requiredText: words.concat(word).join(", ")}, true);
    };
    wordInput.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === ",") { event.preventDefault(); addWord(); }
      else if (event.key === "Backspace" && !wordInput.value) {
        const words = requiredWords(); if (words.length) saveQuick({requiredText: words.slice(0, -1).join(", ")}, true);
      }
    });
    wordInput.addEventListener("blur", addWord);
    tags.addEventListener("click", event => {
      const remove = event.target.closest("[data-remove-word]");
      if (remove) { saveQuick({requiredText: requiredWords().filter(w => w !== remove.dataset.removeWord).join(", ")}, true); return; }
      if (event.target === tags) wordInput.focus();
    });

    // Temas: la misma lista con −/+/++ que en los ajustes finos.
    const prefs = form.querySelector("#qpPrefs");
    prefs.innerHTML = window.CorradiCompatibility.taxonomy.map(concept =>
      '<div class="qp-pref" data-concept="' + concept.id + '"><span class="qp-pref-name">' + esc(concept.label) + '</span><span class="qp-pref-state"></span><span class="qp-pref-btns">' +
      '<button type="button" data-mode="avoid" title="Evitar" aria-label="Evitar ' + esc(concept.label) + '">−</button>' +
      '<button type="button" data-mode="positive" title="Me interesa" aria-label="Me interesa ' + esc(concept.label) + '">+</button>' +
      '<button type="button" data-mode="required" title="Muy importante" aria-label="Muy importante ' + esc(concept.label) + '">++</button></span></div>').join("");
    prefs.addEventListener("click", event => {
      const button = event.target.closest("button[data-mode]"); if (!button) return;
      const id = button.closest(".qp-pref").dataset.concept, mode = button.dataset.mode;
      const priorities = Object.assign({}, profile().priorities || {});
      if (priorities[id] === mode) delete priorities[id];
      else {
        if (mode === "required" || mode === "positive") {
          const limit = mode === "required" ? 2 : 5;
          if (Object.keys(priorities).filter(k => k !== id && priorities[k] === mode).length >= limit) { toast(mode === "required" ? "Máximo 2 temas muy importantes" : "Máximo 5 temas en «me interesa»"); return; }
        }
        priorities[id] = mode;
      }
      saveQuick({priorities}, true);
    });
    form.querySelector("#qpReset").onclick = () => { localStorage.removeItem(KEYS.profile); saveQuick({}, true); toast("Perfil borrado"); };
    syncQuickProfile();
  }
  function syncQuickProfile() {
    const form = document.getElementById("quickProfile");
    if (!form || !form.dataset.ready) return;
    const p = profile(), priorities = p.priorities || {};
    const ageInput = form.querySelector("#qpAge"), out = form.querySelector("#qpAgeOut");
    if (document.activeElement !== ageInput) ageInput.value = p.age || 22;
    out.textContent = p.age ? p.age + " años" : "Sin indicar";
    form.classList.toggle("no-age", !p.age);
    form.querySelectorAll("[data-type]").forEach(chip => chip.setAttribute("aria-pressed", String((p.type || "") === chip.dataset.type)));
    const words = requiredWords(p), tags = form.querySelector("#qpTags"), input = form.querySelector("#qpWordInput");
    tags.querySelectorAll(".qp-tag").forEach(tag => tag.remove());
    input.insertAdjacentHTML("beforebegin", words.map(w => '<span class="qp-tag"><span aria-hidden="true">★</span>' + esc(w) + '<button type="button" data-remove-word="' + esc(w) + '" aria-label="Quitar ' + esc(w) + '">×</button></span>').join(""));
    input.hidden = words.length >= 3;
    form.querySelector("#qpWordCount").textContent = words.length + "/3";
    form.querySelectorAll(".qp-pref").forEach(row => {
      const state = priorities[row.dataset.concept] || "";
      row.dataset.state = state;
      row.querySelector(".qp-pref-state").textContent = PREF_LABEL[state] || "";
      row.querySelectorAll("button[data-mode]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === state)));
    });
    const topics = Object.values(priorities).filter(v => v !== "avoid").length;
    const summary = document.getElementById("qpSummary");
    if (summary) summary.textContent = p.age ? [p.age + " años", p.type ? TYPE_SHORT[p.type] : "Todo", topics ? topics + (topics === 1 ? " tema" : " temas") : "", words.length ? words.length + (words.length === 1 ? " palabra" : " palabras") : ""].filter(Boolean).join(" · ") : "Sin completar";
  }
  function showInCatalog() {
    const p = profile(), type = document.getElementById("type"), age = document.getElementById("age");
    if (type) { type.value = p.type || ""; type.dispatchEvent(new Event("change", {bubbles:true})); }
    if (age) { age.value = p.age || ""; age.dispatchEvent(new Event("input", {bubbles:true})); }
    const target = document.getElementById("explorar"); if (target) target.scrollIntoView({behavior:"smooth", block:"start"});
  }
  function animateCount(node, to) {
    const from = Number(node.dataset.value || to);
    node.dataset.value = to;
    if (from === to || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { node.textContent = to; return; }
    const t0 = performance.now(), dur = 350;
    (function step(now) {
      const k = Math.min(1, (now - t0) / dur);
      node.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
      if (k < 1 && node.dataset.value == to) requestAnimationFrame(step);
    })(t0);
  }
  function matchCard(project, result, showScore) {
    const days = daysLeft(project), img = imageFor(project);
    const badge = showScore && result && result.score != null ? result.score + "%" : (days == null ? "" : Math.max(days, 0) + " d");
    return '<a class="qp-card" data-id="' + esc(project.identifier) + '" href="' + projectUrl(project) + '">' +
      '<span class="qp-card-img"' + (img ? ' style="background-image:url(\'' + esc(img) + '\')"' : '') + '>' + (badge ? '<span class="qp-card-badge' + (showScore ? '' : ' is-date') + '">' + badge + '</span>' : '') + '<span class="qp-card-type">' + esc(TYPE_SHORT[project.type] || "") + '</span></span>' +
      '<span class="qp-card-body"><span class="qp-card-title">' + esc(project.title) + '</span><span class="qp-card-meta">' + flag(project.country_code) + ' ' + esc(COUNTRIES[project.country_code] || project.country_code || "") + ' · ' + deadlineLabel(days) + '</span></span></a>';
  }
  function renderTopMatches() {
    syncQuickProfile();
    const holder = document.getElementById("productMatches");
    if (!holder || !catalog.length) return;
    const p = profile();
    const open = catalog.filter(project => { const d = daysLeft(project); return d == null || d >= 0; });
    const byType = open.filter(project => !p.type || project.type === p.type || (p.type === "VOLUNTEERING" && project.type === "ESC"));
    // Desempate: con la misma afinidad, primero lo que cierra antes y después lo que está más
    // cerca (desde Madrid si vives en España; fuera de España no sabemos la ciudad de origen).
    const home = ORIGINS.madrid;
    const km = project => home && project.latitude != null && project.longitude != null ? distance(home, [Number(project.latitude), Number(project.longitude)]) : 99999;
    const soonest = (a, b) => { const da = daysLeft(a.project), db = daysLeft(b.project); return ((da == null ? 9999 : da) - (db == null ? 9999 : db)) || (km(a.project) - km(b.project)); };
    let fits, excluded = 0, headline, sub, hasTopics = false;
    if (!p.age) {
      fits = byType.map(project => ({project, result: null}));
      headline = "abiertas ahora"; sub = "Indica tu edad y verás solo las que te admiten.";
    } else {
      const evaluated = byType.map(project => ({project, result: eligibility(project, p)}));
      fits = evaluated.filter(x => x.result.state !== "no");
      excluded = evaluated.length - fits.length;
      hasTopics = Object.keys(p.priorities || {}).length > 0 || !!(p.requiredText || "").trim();
      headline = "encajan contigo";
      sub = excluded ? excluded + " descartadas por edad o requisitos." : "Ninguna descartada por edad o requisitos.";
    }
    const top = fits.slice().sort((a, b) => hasTopics ? ((b.result.score || 0) - (a.result.score || 0)) || soonest(a, b) : soonest(a, b)).slice(0, 6);
    let shell = holder.querySelector(".qp-results");
    if (!shell) {
      holder.innerHTML = '<div class="qp-results"><div class="qp-head"><div class="qp-big"><b id="qpCount">0</b><span id="qpHeadline"></span></div><p class="qp-note" id="qpSub"></p></div><span class="matches-title" id="qpListTitle"></span><div class="qp-grid" id="qpGrid"></div><div class="qp-actions"><button type="button" class="qp-cta" id="qpShowAll"></button><a class="directory-link" href="/guia">Antes de solicitar: lee la guía →</a></div></div>';
      shell = holder.querySelector(".qp-results");
      holder.querySelector("#qpShowAll").onclick = showInCatalog;
    }
    animateCount(holder.querySelector("#qpCount"), fits.length);
    holder.querySelector("#qpHeadline").textContent = headline;
    holder.querySelector("#qpSub").textContent = sub;
    holder.querySelector("#qpListTitle").textContent = hasTopics ? "Las que más encajan con tus temas" : "Las que cierran antes";
    holder.querySelector("#qpShowAll").textContent = fits.length ? "Ver las " + fits.length + " en el catálogo →" : "Ver el catálogo →";
    // FLIP: guardamos la posición de cada tarjeta, re-renderizamos y animamos desde la posición antigua.
    const grid = holder.querySelector("#qpGrid"), before = {};
    grid.querySelectorAll(".qp-card").forEach(card => { before[card.dataset.id] = card.getBoundingClientRect(); });
    grid.innerHTML = top.length ? top.map(x => matchCard(x.project, x.result, hasTopics)).join("") : '<div class="qp-empty">No hay ninguna abierta para este perfil ahora mismo. Prueba con otro formato: se añaden nuevas cada día.</div>';
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    grid.querySelectorAll(".qp-card").forEach(card => {
      const old = before[card.dataset.id], now = card.getBoundingClientRect();
      if (old) {
        const dx = old.left - now.left, dy = old.top - now.top;
        if (dx || dy) card.animate([{transform: "translate(" + dx + "px," + dy + "px)"}, {transform: "none"}], {duration: 380, easing: "cubic-bezier(.2,.8,.2,1)"});
      } else card.animate([{opacity: 0, transform: "scale(.94)"}, {opacity: 1, transform: "none"}], {duration: 320, easing: "ease-out"});
    });
  }

  function enhanceCards() {
    document.querySelectorAll(".card[data-id],.top-project[data-id],.mini-card[data-id]").forEach(card => {
      const project = byId(card.dataset.id);
      if (!project) return;
      const result = eligibility(project);
      if (!card.querySelector(".eligibility-chip")) {
        const chip = document.createElement("span");
        chip.className = "eligibility-chip " + result.state;
        chip.textContent = result.state === "yes" ? "✓ " + result.label : result.label;
        chip.title = result.reasons.join(" · ");
        const deadline = card.querySelector(".overlay-deadline,.deadline");
        const host = card.querySelector(".prototype-copy") || card;
        if (deadline) host.insertBefore(chip, deadline); else host.appendChild(chip);
      } else {
        const chip = card.querySelector(".eligibility-chip"), label = result.state === "yes" ? "✓ " + result.label : result.label;
        chip.className = "eligibility-chip " + result.state;
        if (chip.textContent !== label) chip.textContent = label;
        chip.title = result.reasons.join(" · ");
      }
    });
  }

  function enhanceDetail() {
    const detail = document.getElementById("detail");
    if (!detail || !detail.children.length || detail.querySelector(".trace-note")) return;
    const identifier = new URLSearchParams(location.search).get("o");
    const project = byId(identifier);
    if (!project) return;
    const result = eligibility(project);
    const head = detail.querySelector(".detail-head");
    if (head) head.insertAdjacentHTML("afterend", '<div class="project-eligibility ' + result.state + '"><strong>' + esc(result.label) + '</strong>' + (result.score == null ? "" : '<span class="compat-confidence">Confianza ' + esc(result.confidence) + '</span>') + '<br>' + esc(result.reasons.slice(0, 3).join(" · ")) + '</div>');
    const actions = detail.querySelector(".detail-actions");
    if (actions) actions.insertAdjacentHTML("beforeend", '<a class="btn" href="' + projectUrl(project) + '">Abrir ficha completa</a>');
    const trace = document.createElement("div"); trace.className = "trace-note";
    trace.innerHTML = "<i></i><span>" + esc(project.infopack_enriched ? "Datos ampliados desde el infopack oficial" : "Ficha estructurada y revisada por Corradi") + " · Actualizada " + esc(fmt((project.updated || project.created || "").slice(0, 10))) + "</span>";
    if (actions) actions.after(trace); else detail.appendChild(trace);
  }

  function updateFilterChips() {
    const holder = document.getElementById("activeFilters"); if (!holder) return;
    const search = document.getElementById("search"), type = document.getElementById("type"), country = document.getElementById("country"), age = document.getElementById("age");
    const items = [];
    if (search && search.value) items.push(["search", "Búsqueda: " + search.value]);
    if (type && type.value) items.push(["type", TYPES[type.value] || type.value]);
    if (country && country.value) items.push(["country", COUNTRIES[country.value] || country.value]);
    if (age && age.value) items.push(["age", age.value + " años"]);
    holder.innerHTML = items.map(item => '<button class="filter-chip" type="button" data-clear-filter="' + item[0] + '">' + esc(item[1]) + '</button>').join("") + (items.length > 1 ? '<button class="filter-chip clear-all" type="button" data-clear-filter="all">Limpiar todo</button>' : "");
    const empty = document.querySelector("#allCards .empty");
    if (empty && items.length && !empty.querySelector("button")) empty.innerHTML = '<strong>No hay coincidencias con estos filtros.</strong><br><button class="product-button" type="button" data-clear-filter="all">Restablecer filtros</button>';
  }

  function modalShell(kind, eyebrow, title, body) {
    const root = document.getElementById("productDialogs") || document.body;
    root.innerHTML = '<dialog class="product-modal" id="productModal" data-kind="' + esc(kind) + '" aria-labelledby="productModalTitle"><div class="product-modal-head"><div><small>' + esc(eyebrow) + '</small><h2 id="productModalTitle">' + esc(title) + '</h2></div><button class="product-close" type="button" aria-label="Cerrar">×</button></div><div class="product-modal-body">' + body + '</div></dialog>';
    const modal = document.getElementById("productModal");
    modal.querySelector(".product-close").onclick = () => modal.close();
    modal.onclick = event => { if (event.target === modal) modal.close(); };
    modal.showModal();
    requestAnimationFrame(() => { const focus = modal.querySelector("input,select,textarea,button:not(.product-close)"); if (focus) focus.focus(); });
    return modal;
  }

  function openProfile() {
    const p = profile();
    const priorities = p.priorities || {};
    const stateLabel = state => ({avoid:"Evitar", positive:"Me interesa", required:"Muy importante"})[state] || "Indiferente";
    const preferenceRows = window.CorradiCompatibility.taxonomy.map(concept => {
      const state = priorities[concept.id] || "";
      const btn = (mode, text, title) => '<button type="button" class="pref-btn" data-mode="' + mode + '" aria-pressed="' + (state === mode) + '" title="' + title + '">' + text + '</button>';
      return '<div class="preference-row" data-concept="' + concept.id + '" data-state="' + state + '"><strong>' + esc(concept.label) + '</strong><div class="pref-buttons">' + btn("avoid", "−", "Evitar") + '<span class="pref-current">' + stateLabel(state) + '</span>' + btn("positive", "+", "Me interesa") + btn("required", "++", "Muy importante") + '</div></div>';
    }).join("");
    const body = '<p class="product-intro">Tu edad comprueba si eres elegible. Tus prioridades, después, calculan cuánto te encaja — nunca al revés.</p><form id="profileForm"><div class="product-grid profile-basics"><div class="product-field"><label for="productAge">Edad · requisito</label><input id="productAge" type="number" min="13" max="99" value="' + esc(p.age || "") + '" required></div><div class="product-field full"><label for="productType">Formato preferido</label><select id="productType"><option value="">Me interesan todos</option>' + Object.keys(TYPES).filter(x => x !== "ESC").map(type => '<option value="' + type + '"' + (p.type === type ? " selected" : "") + '>' + TYPES[type] + '</option>').join("") + '</select></div></div><div class="priority-heading"><div><span>Prioridades temáticas</span><h3>Indica qué debe pesar de verdad.</h3></div><p><b>Muy importante</b> baja mucho la afinidad si falta · <b>Me interesa</b> suma · <b>Evitar</b> resta si aparece. Máximo 2 muy importantes y 5 interesantes.</p></div><div class="preference-list">' + preferenceRows + '</div><div class="required-heading"><div><span>Nivel máximo</span><h3>Esto tiene que aparecer sí o sí.</h3></div><p>No es una prioridad más: si no lo encontramos en la ficha extendida o el infopack, la afinidad baja fuerte.</p></div><div class="product-field full required-field"><label for="productRequiredText">Imprescindible que la oportunidad incluya (máx. 3 palabras)</label><input id="productRequiredText" maxlength="140" placeholder="Ej. deporte, aire libre" value="' + esc(p.requiredText || "") + '"><small>Sepáralo por comas si son varias cosas.</small></div><div class="privacy-note"><b>Guardado local:</b><span>Permanece solo en este navegador y dispositivo. No se envía al servidor. “Evitar” expresa una preferencia, nunca un requisito oficial de participación.</span></div><div class="affinity-help"><button type="button" class="info-q" data-note="affinityNote" aria-expanded="false" aria-label="Cómo se calcula la afinidad">?</button><span>¿Cómo se calcula el % de afinidad?</span></div><p class="info-note" id="affinityNote">El % dice qué parte de lo que buscas cubre cada oportunidad:<br><br>&bull; <b>Me interesa</b> cuenta 1 y <b>Muy importante</b> cuenta 2. El texto de <b>Imprescindible</b> también cuenta 2.<br>&bull; Cuenta entero si es el tema principal, un 60 % si sale en el título o los objetivos y un 25 % si solo se menciona de pasada.<br>&bull; Si falta algo muy importante o imprescindible, la afinidad no pasa del 40 %.<br>&bull; Cada tema marcado como <b>Evitar</b> que sea central resta 30 puntos.<br>&bull; Si la ficha tiene poca información, no pasa del 70 %.<br><br>El formato no suma: sirve para filtrar. Y la afinidad nunca decide si puedes participar: eso solo lo decide tu edad.<br><br>Consejo: marca pocas cosas, pero las que de verdad te importen.</p><div class="product-form-actions"><button class="product-button danger" id="clearProfile" type="button">Borrar datos</button><button class="product-button primary" type="submit">Guardar y recalcular</button></div></form>';
    const modal = modalShell("profile", "Compatibilidad sin registro", "Mi compatibilidad", body);
    modal.querySelectorAll(".info-q").forEach(q => q.onclick = () => {
      const note = modal.querySelector("#" + q.dataset.note), open = note.getAttribute("data-open") !== "true";
      note.setAttribute("data-open", String(open)); q.setAttribute("aria-expanded", String(open));
    });
    modal.querySelectorAll(".pref-btn").forEach(button => button.onclick = () => {
      const row = button.closest(".preference-row"), mode = button.dataset.mode, current = row.dataset.state, next = current === mode ? "" : mode;
      if (next === "required" || next === "positive") {
        const limit = next === "required" ? 2 : 5;
        const used = Array.from(modal.querySelectorAll(".preference-row")).filter(other => other !== row && other.dataset.state === next).length;
        if (used >= limit) { toast(next === "required" ? "Elige como máximo 2 muy importantes" : "Elige como máximo 5 en 'Me interesa'"); return; }
      }
      row.dataset.state = next;
      row.querySelectorAll(".pref-btn").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === next)));
      row.querySelector(".pref-current").textContent = stateLabel(next);
    });
    modal.querySelector("#profileForm").onsubmit = event => {
      event.preventDefault(); const selected = {}; modal.querySelectorAll(".preference-row").forEach(row => { if (row.dataset.state) selected[row.dataset.concept] = row.dataset.state; });
      const next = {age:modal.querySelector("#productAge").value,residence:"ES",type:modal.querySelector("#productType").value,priorities:selected,requiredText:modal.querySelector("#productRequiredText").value.trim()};
      write(KEYS.profile, next); const age = document.getElementById("age"); if (age && next.age) { age.value = next.age; age.dispatchEvent(new Event("input", {bubbles:true})); } updateSummaries(); enhanceCards(); modal.close(); toast("Perfil guardado en este dispositivo");
    };
    modal.querySelector("#clearProfile").onclick = () => { localStorage.removeItem(KEYS.profile); localStorage.removeItem("corradi-profile-v2"); updateSummaries(); enhanceCards(); modal.close(); toast("Perfil eliminado"); };
  }

  function addApplication(project) {
    const data = applications();
    if (!data[project.identifier]) data[project.identifier] = {status:"preparing", updated:new Date().toISOString(), note:"", title:project.title};
    write(KEYS.applications, data); beacon(project.identifier, "application"); updateSummaries(); toast("Añadida a Mis solicitudes");
  }
  function openApplications() {
    const data = applications(), ids = Object.keys(data), changes = read(KEYS.changes, {}), old = read(KEYS.snapshots, {});
    const rows = ids.map(id => { const project = byId(id), item = data[id], change = changes[id], title = project ? project.title : item.title || (old[id] && old[id].title) || id; return '<div class="application-row"><div><h3>' + (project ? '<a href="' + projectUrl(project) + '">' + esc(title) + '</a>' : esc(title)) + '</h3><p>' + (project ? esc(COUNTRIES[project.country_code] || project.country_code || "") + ' · Límite ' + esc(fmt(project.application_deadline)) : 'No aparece ahora en el catálogo abierto') + '</p>' + (change ? '<div class="change-alert">Cambio: ' + esc(change.labels.join(" · ")) + '</div>' : '') + '</div><select data-application-status="' + esc(id) + '" aria-label="Estado de ' + esc(title) + '">' + Object.keys(STATUS).map(value => '<option value="' + value + '"' + (item.status === value ? " selected" : "") + '>' + STATUS[value] + '</option>').join("") + '</select><button type="button" data-application-remove="' + esc(id) + '" aria-label="Quitar">×</button></div>'; }).join("");
    const modal = modalShell("applications", "Seguimiento y alertas", "Mis solicitudes", '<p class="product-intro">Corradi compara fechas, enlaces, edad y países publicados desde tu última visita. Todo permanece en este dispositivo.</p><div class="product-list">' + (rows || '<div class="product-empty">Todavía no sigues ninguna solicitud. Abre una oportunidad y pulsa “Preparar solicitud”.</div>') + '</div>');
    Object.keys(changes).forEach(id => { changes[id].seen = true; }); write(KEYS.changes, changes); updateChangeCount();
    modal.querySelectorAll("[data-application-status]").forEach(select => select.onchange = () => { const next = applications(); next[select.dataset.applicationStatus].status = select.value; next[select.dataset.applicationStatus].updated = new Date().toISOString(); write(KEYS.applications, next); updateSummaries(); toast("Estado actualizado"); });
    modal.querySelectorAll("[data-application-remove]").forEach(button => button.onclick = () => { const next = applications(); delete next[button.dataset.applicationRemove]; write(KEYS.applications, next); updateSummaries(); openApplications(); });
  }

  function toggleCompare(project) {
    let ids = compareIds();
    if (ids.includes(project.identifier)) ids = ids.filter(id => id !== project.identifier);
    else if (ids.length >= 3) return toast("Puedes comparar hasta 3 oportunidades");
    else { ids.push(project.identifier); beacon(project.identifier, "compare"); }
    write(KEYS.compare, ids); updateSummaries(); enhanceCards(); toast(ids.includes(project.identifier) ? "Añadida al comparador" : "Quitada del comparador");
  }
  function openCompare() {
    const projects = compareIds().map(byId).filter(Boolean);
    let body = '<p class="product-intro">Compara hasta tres oportunidades con los mismos criterios.</p>';
    if (!projects.length) body += '<div class="product-empty">No has seleccionado ninguna. Usa el botón “Comparar” de las tarjetas.</div>';
    else {
      const row = (label, getter) => '<tr><td>' + esc(label) + '</td>' + projects.map(project => '<td>' + esc(getter(project) || "Por confirmar") + '</td>').join("") + '</tr>';
      body += '<div class="compare-scroll"><table class="compare-table"><thead><tr><th>Criterio</th>' + projects.map(p => '<th><a href="' + projectUrl(p) + '">' + esc(p.title) + '</a></th>').join("") + '</tr></thead><tbody>' + row("Tipo", p => TYPES[p.type]) + row("Destino", p => [p.location, COUNTRIES[p.country_code]].filter(Boolean).join(", ")) + row("Fechas", p => fmt(p.start_date) + " — " + fmt(p.end_date)) + row("Plazo", p => fmt(p.application_deadline)) + row("Edad", p => p.participant_min_age || p.participant_max_age ? (p.participant_min_age || "—") + "–" + (p.participant_max_age || "+") : "Consultar") + row("Coste", p => p.cost) + row("Compatibilidad", p => eligibility(p).label) + '</tbody></table></div><div class="product-form-actions"><button class="product-button danger" id="clearCompare" type="button">Vaciar comparador</button></div>';
    }
    const modal = modalShell("compare", "Decidir mejor", "Comparar oportunidades", body);
    const clear = modal.querySelector("#clearCompare"); if (clear) clear.onclick = () => { write(KEYS.compare, []); updateSummaries(); enhanceCards(); openCompare(); };
  }

  function projectOptions(selected) { return catalog.map(project => '<option value="' + esc(project.identifier) + '"' + (selected === project.identifier ? " selected" : "") + '>' + esc(project.title) + '</option>').join(""); }
  function checklistFor(project) {
    const allDocs = documents(), current = allDocs[project.identifier] || {};
    const extra = project.type === "VOLUNTEERING" || project.type === "ESC" ? ["Certificado de antecedentes, si lo solicita la organización"] : ["Acuerdo sobre desplazamiento con la organización de envío"];
    return DEFAULT_DOCS.concat(extra).map((label, index) => '<label class="check-item ' + (current[index] ? "done" : "") + '"><input type="checkbox" data-doc-index="' + index + '"' + (current[index] ? " checked" : "") + '><span>' + esc(label) + '</span></label>').join("");
  }
  function openDocuments(identifier) {
    const project = byId(identifier) || catalog[0]; if (!project) return toast("No hay oportunidades disponibles");
    const body = '<div class="product-field"><label for="docProject">Oportunidad</label><select id="docProject">' + projectOptions(project.identifier) + '</select></div><p class="product-intro">Lista orientativa. Revisa siempre el infopack porque cada organización puede pedir documentos diferentes.</p><div class="checklist" id="documentChecklist">' + checklistFor(project) + '</div>';
    const modal = modalShell("documents", "Preparación", "Lista de documentos", body);
    const bind = selected => { modal.querySelectorAll("[data-doc-index]").forEach(input => input.onchange = () => { const data = documents(); data[selected] = data[selected] || {}; data[selected][input.dataset.docIndex] = input.checked; write(KEYS.documents, data); input.closest(".check-item").classList.toggle("done", input.checked); }); };
    bind(project.identifier);
    modal.querySelector("#docProject").onchange = event => { const selected = byId(event.target.value); modal.querySelector("#documentChecklist").innerHTML = checklistFor(selected); bind(selected.identifier); };
  }

  function radians(value) { return value * Math.PI / 180; }
  function distance(a, b) { const dLat = radians(b[0]-a[0]), dLon = radians(b[1]-a[1]), x = Math.sin(dLat/2) ** 2 + Math.cos(radians(a[0])) * Math.cos(radians(b[0])) * Math.sin(dLon/2) ** 2; return 6371 * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1-x)); }
  function openTravel(identifier) {
    const project = byId(identifier) || catalog.find(item => item.latitude != null); if (!project) return toast("No hay destinos disponibles");
    const body = '<p class="product-intro">Estimación orientativa. Introduce el límite de reembolso que figure en el infopack; Corradi no sustituye la confirmación de la organización.</p><form id="travelForm"><div class="product-grid"><div class="product-field"><label for="travelProject">Oportunidad</label><select id="travelProject">' + projectOptions(project.identifier) + '</select></div><div class="product-field"><label for="travelOrigin">Ciudad de salida</label><select id="travelOrigin">' + Object.keys(ORIGINS).map(city => '<option value="' + city + '">' + city[0].toUpperCase() + city.slice(1) + '</option>').join("") + '</select></div><div class="product-field"><label for="ticketCost">Coste total estimado (€)</label><input id="ticketCost" type="number" min="0" step="1" value="0"></div><div class="product-field"><label for="refundLimit">Reembolso máximo del infopack (€)</label><input id="refundLimit" type="number" min="0" step="1" value="0"></div></div><div class="product-form-actions"><button class="product-button primary" type="submit">Calcular viaje</button></div></form><div id="travelResult"></div>';
    const modal = modalShell("travel", "Planificación", "Calculadora de viaje", body);
    modal.querySelector("#travelForm").onsubmit = event => { event.preventDefault(); const selected = byId(modal.querySelector("#travelProject").value), origin = ORIGINS[modal.querySelector("#travelOrigin").value], target = [Number(selected.latitude), Number(selected.longitude)], cost = Number(modal.querySelector("#ticketCost").value || 0), limit = Number(modal.querySelector("#refundLimit").value || 0); if (!Number.isFinite(target[0]) || !Number.isFinite(target[1])) return toast("Ese destino no tiene coordenadas suficientes"); const km = Math.round(distance(origin, target) * 1.18), out = Math.max(0, cost-limit), suggestion = km < 800 ? "Compara tren y autobús antes de volar." : "Compara rutas aéreas y ferroviarias; confirma los días de viaje elegibles."; modal.querySelector("#travelResult").innerHTML = '<div class="tool-result"><strong>≈ ' + km.toLocaleString("es") + ' km</strong><p>Distancia de ruta estimada · gasto no cubierto: <b>' + out.toFixed(0) + ' €</b>. ' + esc(suggestion) + '</p></div>'; };
  }

  function icsEscape(value) { return String(value || "").replace(/\\/g,"\\\\").replace(/\n/g,"\\n").replace(/,/g,"\\,").replace(/;/g,"\\;"); }
  function downloadCalendar(project) {
    const compact = value => String(value || "").replaceAll("-", "");
    const events = [];
    if (project.application_deadline) events.push(["Cierra la solicitud: " + project.title, compact(project.application_deadline), "Revisar y enviar la candidatura"]);
    if (project.start_date) events.push(["Comienza: " + project.title, compact(project.start_date), "Oportunidad Corradi en " + (COUNTRIES[project.country_code] || project.country_code || "Europa")]);
    if (!events.length) return toast("Esta oportunidad aún no tiene fechas confirmadas");
    const lines = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Corradi//Oportunidades//ES","CALSCALE:GREGORIAN"];
    events.forEach((event, index) => lines.push("BEGIN:VEVENT","UID:" + project.identifier + "-" + index + "@corradi","DTSTART;VALUE=DATE:" + event[1],"SUMMARY:" + icsEscape(event[0]),"DESCRIPTION:" + icsEscape(event[2] + " · " + location.origin + projectUrl(project)),"END:VEVENT")); lines.push("END:VCALENDAR");
    const anchor = document.createElement("a"); anchor.href = URL.createObjectURL(new Blob([lines.join("\r\n")], {type:"text/calendar;charset=utf-8"})); anchor.download = "corradi-" + project.identifier.replace("CORRADI-", "") + ".ics"; anchor.click(); setTimeout(() => URL.revokeObjectURL(anchor.href), 1000); beacon(project.identifier, "calendar"); toast("Calendario descargado");
  }

  function openAssistant(identifier) {
    const project = byId(identifier) || catalog[0]; if (!project) return toast("No hay oportunidades disponibles");
    const body = '<p class="product-intro">El asistente organiza únicamente lo que escribas aquí. Estos datos se usan para generar el borrador y no se guardan en tu perfil.</p><form id="assistantForm"><div class="product-grid"><div class="product-field full"><label for="assistantProject">Oportunidad</label><select id="assistantProject">' + projectOptions(project.identifier) + '</select></div><div class="product-field"><label for="assistantTask">Qué necesitas</label><select id="assistantTask"><option value="motivation">Explicar mi motivación</option><option value="why_me">Qué puedo aportar</option><option value="experience">Presentar mi experiencia</option><option value="review">Revisar mi borrador</option></select></div><div class="product-field"><label for="assistantMotivation">Motivación real</label><textarea id="assistantMotivation" placeholder="¿Por qué te interesa de verdad?"></textarea></div><div class="product-field"><label for="assistantExperience">Experiencia que quieras mencionar · no se guarda</label><textarea id="assistantExperience" placeholder="Voluntariado, estudios o proyectos reales"></textarea></div><div class="product-field"><label for="assistantStrengths">Qué puedes aportar · no se guarda</label><textarea id="assistantStrengths" placeholder="Fortalezas o formas de contribuir al grupo"></textarea></div><div class="product-field full"><label for="assistantLanguages">Idiomas relevantes · no se guardan</label><input id="assistantLanguages" maxlength="120" placeholder="Ej. inglés B1, español nativo"></div><div class="product-field full"><label for="assistantDraft">Borrador existente (opcional)</label><textarea id="assistantDraft" placeholder="Pega aquí la pregunta o tu texto"></textarea></div></div><div class="product-form-actions"><button class="product-button primary" id="assistantSubmit" type="submit">Crear borrador responsable</button></div></form><div id="assistantResult"></div>';
    const modal = modalShell("assistant", "Ayuda de redacción", "Preparar candidatura", body);
    modal.querySelector("#assistantForm").onsubmit = event => { event.preventDefault(); const button = modal.querySelector("#assistantSubmit"); button.disabled = true; button.textContent = "Preparando…"; const selected = modal.querySelector("#assistantProject").value; fetch("/api/application-assistant", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({identifier:selected,task:modal.querySelector("#assistantTask").value,draft:modal.querySelector("#assistantDraft").value,motivation:modal.querySelector("#assistantMotivation").value,experience:modal.querySelector("#assistantExperience").value,strengths:modal.querySelector("#assistantStrengths").value,languages:modal.querySelector("#assistantLanguages").value})}).then(response => { if (!response.ok) throw Error(); return response.json(); }).then(result => { modal.querySelector("#assistantResult").innerHTML = '<div class="assistant-output"><textarea id="assistantOutput">' + esc(result.draft || "") + '</textarea></div>'; const output = modal.querySelector(".assistant-output"); output.insertAdjacentHTML("beforeend", '<ul>' + (result.tips || []).map(tip => '<li>' + esc(tip) + '</li>').join("") + '</ul><p class="notice">' + esc(result.notice || "Revisa siempre el borrador antes de enviarlo.") + '</p><button class="product-button" id="copyAssistant" type="button">Copiar texto</button>'); output.querySelector("#copyAssistant").onclick = () => navigator.clipboard.writeText(modal.querySelector("#assistantOutput").value).then(() => toast("Borrador copiado")); beacon(selected, "assistant"); }).catch(() => { modal.querySelector("#assistantResult").innerHTML = '<div class="product-empty">El asistente no está disponible ahora. Conserva tu texto y prueba más tarde.</div>'; }).finally(() => { button.disabled = false; button.textContent = "Crear borrador responsable"; }); };
  }

  function openCalendarTool(identifier) {
    const project = byId(identifier) || catalog[0]; if (!project) return;
    const modal = modalShell("calendar", "Fechas", "Añadir al calendario", '<p class="product-intro">Descarga un archivo compatible con Apple Calendar, Google Calendar y Outlook.</p><div class="product-field"><label for="calendarProject">Oportunidad</label><select id="calendarProject">' + projectOptions(project.identifier) + '</select></div><div class="product-form-actions"><button class="product-button primary" id="downloadCalendar" type="button">Descargar .ics</button></div>');
    modal.querySelector("#downloadCalendar").onclick = () => downloadCalendar(byId(modal.querySelector("#calendarProject").value));
  }
  function openTools() {
    const body = '<p class="product-intro">Elige una herramienta para preparar la oportunidad sin perder información.</p><div class="tool-tabs"><button type="button" data-tool="documents">Documentos</button><button type="button" data-tool="travel">Viaje y reembolso</button><button type="button" data-tool="calendar">Calendario</button><button type="button" data-tool="assistant">Asistente de candidatura</button></div><div class="product-empty">Selecciona una herramienta.</div>';
    const modal = modalShell("tools", "Preparación", "Herramientas", body);
    modal.querySelectorAll("[data-tool]").forEach(button => button.onclick = () => { modal.close(); ({documents:openDocuments,travel:openTravel,calendar:openCalendarTool,assistant:openAssistant})[button.dataset.tool](); });
  }

  function enhanceProjectPage(project) {
    currentProject = project;
    const card = document.querySelector(".apply-card"); if (!card || card.querySelector(".project-product-card")) return;
    const result = eligibility(project);
    card.insertAdjacentHTML("afterbegin", '<div class="project-eligibility ' + result.state + '"><strong>' + esc(result.label) + '</strong>' + (result.score == null ? "" : '<span class="compat-confidence">Confianza ' + esc(result.confidence) + '</span>') + '<br>' + esc(result.reasons.slice(0, 3).join(" · ")) + '</div>');
    card.insertAdjacentHTML("beforeend", '<div class="project-product-card"><h3>Antes de solicitar</h3><div class="project-product-actions"><a href="/guia">Consultar la guía Erasmus+</a><button type="button" data-product-open="profile">Ajustar mi compatibilidad</button></div><div class="trace-note"><i></i><span>' + esc(project.infopack_enriched ? "Ampliada desde el infopack oficial" : "Datos estructurados por Corradi") + ' · ' + esc(fmt((project.updated || project.created || "").slice(0,10))) + '</span></div></div>');
  }

  function routeAction(action, identifier) {
    const project = byId(identifier) || currentProject;
    if (action === "compare" && project) toggleCompare(project);
    else if (action === "application" && project) { addApplication(project); openAssistant(project.identifier); }
    else if (action === "documents") openDocuments(identifier);
    else if (action === "travel") openTravel(identifier);
    else if (action === "calendar") openCalendarTool(identifier);
    else if (action === "assistant") openAssistant(identifier);
  }

  function bindGlobal() {
    document.addEventListener("click", event => {
      const opener = event.target.closest("[data-product-open]");
      if (opener) { event.preventDefault(); if (opener.dataset.productOpen === "profile") openProfile(); return; }
      const action = event.target.closest("[data-product-action]");
      if (action) { event.preventDefault(); event.stopPropagation(); routeAction(action.dataset.productAction, action.dataset.id); return; }
      const clear = event.target.closest("[data-clear-filter]");
      if (clear) { const value = clear.dataset.clearFilter; ["search","type","country","age"].forEach(id => { if (value !== "all" && value !== id) return; const field = document.getElementById(id); if (field) { field.value = ""; field.dispatchEvent(new Event(id === "search" || id === "age" ? "input" : "change", {bubbles:true})); } }); updateFilterChips(); }
    }, true);
    ["search","type","country","age"].forEach(id => { const field = document.getElementById(id); if (field) field.addEventListener(id === "search" || id === "age" ? "input" : "change", () => setTimeout(updateFilterChips)); });
  }

  function setupInstall() {
    const button = document.getElementById("installApp");
    let prompt = null;
    window.addEventListener("beforeinstallprompt", event => {
      event.preventDefault(); prompt = event;
      if (button) { button.hidden = false; button.onclick = async () => { await prompt.prompt(); prompt = null; button.hidden = true; }; }
    });
    window.addEventListener("appinstalled", () => { if (button) button.hidden = true; toast("Corradi se ha instalado"); });
    if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }
  function initHome(data) {
    catalog = data.results || []; generated = data.generated || "";
    bindGlobal(); setupInstall(); setupQuickProfile(); updateSummaries(); updateFilterChips(); enhanceCards(); enhanceDetail();
    const observer = new MutationObserver(() => { enhanceCards(); enhanceDetail(); updateFilterChips(); });
    ["allCards","urgentCards","weeklyTop","rowSoon","rowYE","rowTC","detail"].forEach(id => { const node = document.getElementById(id); if (node) observer.observe(node, {childList:true, subtree:true}); });
    if (new URLSearchParams(location.search).get("profile") === "1") setTimeout(openProfile, 0);
  }
  function initProject(data) {
    catalog = [data]; currentProject = data; bindGlobal(); setupInstall(); setupQuickProfile(); updateSummaries();
    const apply = () => enhanceProjectPage(data); apply();
    const app = document.getElementById("app"); if (app) new MutationObserver(apply).observe(app, {childList:true, subtree:true});
  }

  const projectMatch = location.pathname.match(/^\/proyecto\/(CORRADI-\d{4}-\d{4})$/);
  const request = projectMatch ? fetch("/opportunities/" + encodeURIComponent(projectMatch[1])).then(r => r.ok ? r.json() : Promise.reject()) : fetch("/api/map").then(r => r.ok ? r.json() : Promise.reject());
  request.then(data => projectMatch ? initProject(data) : initHome(data)).catch(() => {});
})();
