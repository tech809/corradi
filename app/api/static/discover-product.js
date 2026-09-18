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
    if (pNode) pNode.textContent = (p.age || p.residence || p.type || Object.keys(p.priorities || {}).length) ? "Guardado en este dispositivo" : "Comprueba requisitos sin registrarte";
    const aNode = document.getElementById("applicationSummary");
    if (aNode) aNode.textContent = Object.keys(apps).length ? Object.keys(apps).length + " en seguimiento" : "Organiza tu progreso";
    const cNode = document.getElementById("compareSummary");
    if (cNode) cNode.textContent = compare.length + (compare.length === 1 ? " seleccionada" : " seleccionadas");
    updateChangeCount();
    renderTopMatches();
  }

  function renderTopMatches() {
    const holder = document.getElementById("productMatches");
    if (!holder) return;
    const p = profile();
    if (!p.age || !p.residence) { holder.innerHTML = '<div class="matches-empty">Configura tu perfil para ver aquí tus mejores oportunidades.</div>'; return; }
    const top = catalog.map(project => ({project, result: eligibility(project, p)}))
      .filter(x => x.result.score != null && x.result.state !== "no")
      .sort((a, b) => b.result.score - a.result.score)
      .slice(0, 3);
    if (!top.length) { holder.innerHTML = '<div class="matches-empty">Añade prioridades a tu perfil para ver aquí tus mejores oportunidades.</div>'; return; }
    holder.innerHTML = '<span class="matches-title">Tus mejores oportunidades ahora mismo</span>' + top.map(({project, result}) =>
      '<a class="product-match" href="' + projectUrl(project) + '"><span class="product-match-score">' + result.score + '%</span><span class="product-match-title">' + esc(project.title) + '</span></a>'
    ).join("");
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
    if (!detail || !detail.children.length || detail.querySelector(".detail-product-bar")) return;
    const identifier = new URLSearchParams(location.search).get("o");
    const project = byId(identifier);
    if (!project) return;
    const result = eligibility(project);
    const head = detail.querySelector(".detail-head");
    if (head) head.insertAdjacentHTML("afterend", '<div class="project-eligibility ' + result.state + '"><strong>' + esc(result.label) + '</strong>' + (result.score == null ? "" : '<span class="compat-confidence">Confianza ' + esc(result.confidence) + '</span>') + '<br>' + esc(result.reasons.slice(0, 3).join(" · ")) + '</div>');
    const actions = detail.querySelector(".detail-actions");
    const bar = document.createElement("div"); bar.className = "detail-product-bar";
    bar.innerHTML = '<a class="strong" href="' + projectUrl(project) + '">Abrir ficha completa</a><button type="button" data-product-open="profile">Ajustar mi compatibilidad</button>';
    if (actions) actions.before(bar); else detail.appendChild(bar);
    const trace = document.createElement("div"); trace.className = "trace-note";
    trace.innerHTML = "<i></i><span>" + esc(project.infopack_enriched ? "Datos ampliados desde el infopack oficial" : "Ficha estructurada y revisada por Corradi") + " · Actualizada " + esc(fmt((project.updated || project.created || "").slice(0, 10))) + "</span>";
    bar.after(trace);
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
    const residence = p.residence || "ES";
    const countryOptions = Object.keys(COUNTRIES).sort((a,b) => COUNTRIES[a].localeCompare(COUNTRIES[b], "es")).map(code => '<option value="' + code + '"' + (residence === code ? " selected" : "") + '>' + esc(COUNTRIES[code]) + '</option>').join("");
    const priorities = p.priorities || {};
    const stateLabel = state => ({avoid:"Evitar", positive:"Me interesa", required:"Muy importante"})[state] || "Indiferente";
    const preferenceRows = window.CorradiCompatibility.taxonomy.map(concept => {
      const state = priorities[concept.id] || "";
      const btn = (mode, text, title) => '<button type="button" class="pref-btn" data-mode="' + mode + '" aria-pressed="' + (state === mode) + '" title="' + title + '">' + text + '</button>';
      return '<div class="preference-row" data-concept="' + concept.id + '" data-state="' + state + '"><strong>' + esc(concept.label) + '</strong><div class="pref-buttons">' + btn("avoid", "−", "Evitar") + '<span class="pref-current">' + stateLabel(state) + '</span>' + btn("positive", "+", "Me interesa") + btn("required", "++", "Muy importante") + '</div></div>';
    }).join("");
    const body = '<p class="product-intro">Primero comprobamos los requisitos oficiales. Después calculamos afinidad con conceptos normalizados en español e inglés, no con coincidencias accidentales de palabras.</p><div class="profile-explainer"><div><b>Requisitos</b><span>Edad y residencia pueden determinar si eres elegible.</span></div><div><b>Afinidad</b><span>Formato y prioridades explican qué encaja contigo y qué no.</span></div></div><form id="profileForm"><div class="product-grid profile-basics"><div class="product-field"><label for="productAge">Edad · requisito</label><input id="productAge" type="number" min="13" max="99" value="' + esc(p.age || "") + '" required></div><div class="product-field"><label for="productResidence">País de residencia · requisito</label><select id="productResidence" required><option value="">Selecciona</option>' + countryOptions + '</select></div><div class="product-field full"><label for="productType">Formato preferido</label><select id="productType"><option value="">Me interesan todos</option>' + Object.keys(TYPES).filter(x => x !== "ESC").map(type => '<option value="' + type + '"' + (p.type === type ? " selected" : "") + '>' + TYPES[type] + '</option>').join("") + '</select></div></div><div class="priority-heading"><div><span>Prioridades temáticas</span><h3>Indica qué debe pesar de verdad.</h3></div><p><b>Muy importante</b> baja mucho la afinidad si falta · <b>Me interesa</b> suma · <b>Evitar</b> resta si aparece. Máximo 2 muy importantes y 5 interesantes.</p></div><div class="preference-list">' + preferenceRows + '</div><div class="required-heading"><div><span>Nivel máximo</span><h3>Esto tiene que aparecer sí o sí.</h3></div><p>No es una prioridad más: si no lo encontramos en la ficha extendida o el infopack, la afinidad baja fuerte.</p></div><div class="product-field full required-field"><label for="productRequiredText">Imprescindible que la oportunidad incluya</label><input id="productRequiredText" maxlength="140" placeholder="Ej. deporte, aire libre" value="' + esc(p.requiredText || "") + '"><small>Sepáralo por comas si son varias cosas.</small></div><div class="privacy-note"><b>Guardado local:</b><span>Permanece solo en este navegador y dispositivo. No se envía al servidor. “Evitar” expresa una preferencia, nunca un requisito oficial de participación.</span></div><div class="affinity-help"><button type="button" class="info-q" data-note="affinityNote" aria-expanded="false" aria-label="Cómo se calcula la afinidad">?</button><span>¿Cómo se calcula el % de afinidad?</span></div><p class="info-note" id="affinityNote">Partimos de una base de 50 puntos sobre 100 y sumamos o restamos según lo que hayas marcado, así:<br><br>&bull; <b>Formato preferido:</b> +15 si coincide con el tipo de proyecto, −10 si no coincide, +10 si no has marcado ninguno.<br>&bull; <b>Muy importante</b> (por tema): +25 si aparece en el título, el tema o los resultados de aprendizaje. −35 si no aparece — es la señal que más pesa, porque dijiste que era imprescindible.<br>&bull; <b>Me interesa</b> (por tema): +7 si aparece en cualquier parte de la ficha, hasta +21 en total.<br>&bull; <b>Evitar</b> (por tema): −25 si aparece de forma central en la ficha.<br>&bull; <b>Imprescindible que la oportunidad incluya</b> (cada palabra): +18 si aparece en la ficha extendida o el infopack — no en el resumen corto —, hasta +36 en total. −40 si no aparece: junto con Muy importante, es lo que más mueve el porcentaje.<br><br>El resultado final siempre queda entre el 5% y el 100%.<br><br>Lo que nunca cambia esta cuenta: la edad y el país de residencia son requisitos oficiales, no preferencias. Si no los cumples, la oportunidad se marca como no disponible para ti, sin importar cuántos temas coincidan.<br><br>Para sacarle el máximo partido: marca pocas cosas, pero las que de verdad te importen. Si marcas muchos temas como "Me interesa" el matiz se diluye; si reservas "Muy importante" e "imprescindible" para lo esencial, el porcentaje refleja mucho mejor si la oportunidad te encaja de verdad.</p><div class="product-form-actions"><button class="product-button danger" id="clearProfile" type="button">Borrar datos</button><button class="product-button primary" type="submit">Guardar y recalcular</button></div></form>';
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
      const next = {age:modal.querySelector("#productAge").value,residence:modal.querySelector("#productResidence").value,type:modal.querySelector("#productType").value,priorities:selected,requiredText:modal.querySelector("#productRequiredText").value.trim()};
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
  function setupMobileNav() {
    if (!document.querySelector(".mobile-bottom-nav")) document.body.insertAdjacentHTML("beforeend", '<nav class="mobile-bottom-nav" aria-label="Navegación móvil"><a href="/">⌂<span>Inicio</span></a><a href="/#explorar">⌕<span>Buscar</span></a><a href="/mapa">⌖<span>Mapa</span></a><a href="/guia">?<span>Guía</span></a><button type="button" data-product-open="profile">◎<span>Perfil</span></button></nav>');
    const nav = document.querySelector(".mobile-bottom-nav");
    nav.querySelectorAll("a,button").forEach(item => item.addEventListener("click", () => { nav.querySelectorAll(".active").forEach(active => active.classList.remove("active")); item.classList.add("active"); }));
  }

  function initHome(data) {
    catalog = data.results || []; generated = data.generated || "";
    setupMobileNav(); bindGlobal(); setupInstall(); updateSummaries(); updateFilterChips(); enhanceCards(); enhanceDetail();
    const observer = new MutationObserver(() => { enhanceCards(); enhanceDetail(); updateFilterChips(); });
    ["allCards","urgentCards","weeklyTop","rowSoon","rowYE","rowTC","detail"].forEach(id => { const node = document.getElementById(id); if (node) observer.observe(node, {childList:true, subtree:true}); });
    if (new URLSearchParams(location.search).get("profile") === "1") setTimeout(openProfile, 0);
  }
  function initProject(data) {
    catalog = [data]; currentProject = data; setupMobileNav(); bindGlobal(); setupInstall(); updateSummaries();
    const apply = () => enhanceProjectPage(data); apply();
    const app = document.getElementById("app"); if (app) new MutationObserver(apply).observe(app, {childList:true, subtree:true});
  }

  const projectMatch = location.pathname.match(/^\/proyecto\/(CORRADI-\d{4}-\d{4})$/);
  const request = projectMatch ? fetch("/opportunities/" + encodeURIComponent(projectMatch[1])).then(r => r.ok ? r.json() : Promise.reject()) : fetch("/api/map").then(r => r.ok ? r.json() : Promise.reject());
  request.then(data => projectMatch ? initProject(data) : initHome(data)).catch(() => {});
})();
