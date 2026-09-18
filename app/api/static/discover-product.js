(function () {
  "use strict";

  const KEYS = {
    profile: "corradi-profile-v2",
    applications: "corradi-applications-v1",
    compare: "corradi-compare-v1",
    documents: "corradi-documents-v1",
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
  function norm(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
  function fmt(value) { return value ? new Intl.DateTimeFormat("es", {day:"numeric", month:"short", year:"numeric"}).format(new Date(value + "T12:00:00")) : "Por confirmar"; }
  function projectUrl(project) { return "/proyecto/" + encodeURIComponent(project.identifier); }
  function byId(identifier) { return catalog.find(project => project.identifier === identifier); }
  function profile() { return read(KEYS.profile, {}); }
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
    data = data || profile();
    let score = 45, known = 0, reasons = [], hardFail = false;
    const age = Number(data.age || 0);
    if (age) {
      known++;
      if ((project.participant_min_age && age < project.participant_min_age) || (project.participant_max_age && age > project.participant_max_age)) {
        hardFail = true; reasons.push("Tu edad no entra en el rango indicado");
      } else { score += 25; reasons.push("Tu edad encaja"); }
    } else reasons.push("Añade tu edad para comprobar el rango");
    if (data.residence) {
      known++;
      if (data.residence !== "ES") { hardFail = true; reasons.push("Este catálogo está validado para residentes en España"); }
      else { score += 20; reasons.push("Residencia compatible con esta edición"); }
    } else reasons.push("Añade tu residencia para verificar elegibilidad");
    if (data.type) {
      known++;
      if (data.type === project.type || (data.type === "VOLUNTEERING" && project.type === "ESC")) { score += 10; reasons.push("Es el tipo de proyecto que buscas"); }
      else score -= 5;
    }
    const interests = norm(data.interests).split(/[,;]+|\s+/).filter(word => word.length > 3);
    if (interests.length) {
      known++;
      const text = norm([project.title, project.topic, project.summary].join(" "));
      const matches = interests.filter(word => text.includes(word));
      if (matches.length) { score += Math.min(15, matches.length * 5); reasons.push("Coincide con " + matches.slice(0, 3).join(", ")); }
    }
    score = Math.max(0, Math.min(100, hardFail ? Math.min(score, 35) : score));
    if (!known) return {score:null, state:"unknown", label:"Completa tu perfil", reasons};
    if (hardFail) return {score, state:"no", label:"Revisa requisitos", reasons};
    if (score >= 80) return {score, state:"yes", label:score + "% compatible", reasons};
    return {score, state:"warn", label:score + "% compatible", reasons};
  }

  function updateSummaries() {
    const p = profile(), apps = applications(), compare = compareIds();
    const pNode = document.getElementById("profileSummary");
    if (pNode) pNode.textContent = p.age || p.residence || p.interests ? "Perfil configurado" : "Calcula tu compatibilidad";
    const aNode = document.getElementById("applicationSummary");
    if (aNode) aNode.textContent = Object.keys(apps).length ? Object.keys(apps).length + " en seguimiento" : "Organiza tu progreso";
    const cNode = document.getElementById("compareSummary");
    if (cNode) cNode.textContent = compare.length + (compare.length === 1 ? " seleccionada" : " seleccionadas");
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
        card.appendChild(chip);
      } else {
        const chip = card.querySelector(".eligibility-chip"), label = result.state === "yes" ? "✓ " + result.label : result.label;
        chip.className = "eligibility-chip " + result.state;
        if (chip.textContent !== label) chip.textContent = label;
      }
      if (card.closest("#allCards") && !card.querySelector(".card-product-actions")) {
        const actions = document.createElement("div"); actions.className = "card-product-actions";
        actions.innerHTML = '<a href="' + projectUrl(project) + '">Ficha completa</a><button type="button" data-product-action="compare" data-id="' + esc(project.identifier) + '">Comparar</button>';
        const deadline = card.querySelector(".overlay-deadline"), host = card.querySelector(".prototype-copy") || card;
        if (deadline) host.insertBefore(actions, deadline); else host.appendChild(actions);
      }
      const compareButton = card.querySelector('[data-product-action="compare"]');
      if (compareButton) compareButton.classList.toggle("compare-on", compareIds().includes(project.identifier));
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
    if (head) head.insertAdjacentHTML("afterend", '<div class="project-eligibility ' + result.state + '"><strong>' + esc(result.label) + '</strong><br>' + esc(result.reasons.slice(0, 2).join(" · ")) + '</div>');
    const actions = detail.querySelector(".detail-actions");
    const bar = document.createElement("div"); bar.className = "detail-product-bar";
    bar.innerHTML = '<a href="' + projectUrl(project) + '">Abrir ficha completa</a><button class="strong" type="button" data-product-action="application" data-id="' + esc(project.identifier) + '">Preparar solicitud</button><button type="button" data-product-action="compare" data-id="' + esc(project.identifier) + '">Comparar</button><button type="button" data-product-action="documents" data-id="' + esc(project.identifier) + '">Documentos</button>';
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
    const countryOptions = Object.keys(COUNTRIES).sort((a,b) => COUNTRIES[a].localeCompare(COUNTRIES[b], "es")).map(code => '<option value="' + code + '"' + (p.residence === code ? " selected" : "") + '>' + esc(COUNTRIES[code]) + '</option>').join("");
    const body = '<p class="product-intro">Usamos estos datos para explicar qué encaja y qué requisito debes revisar. No salen de este navegador.</p><form id="profileForm"><div class="product-grid"><div class="product-field"><label for="productAge">Edad</label><input id="productAge" type="number" min="13" max="99" value="' + esc(p.age || "") + '" required></div><div class="product-field"><label for="productResidence">País de residencia</label><select id="productResidence" required><option value="">Selecciona</option>' + countryOptions + '</select></div><div class="product-field"><label for="productType">Tipo preferido</label><select id="productType"><option value="">Cualquiera</option>' + Object.keys(TYPES).filter(x => x !== "ESC").map(type => '<option value="' + type + '"' + (p.type === type ? " selected" : "") + '>' + TYPES[type] + '</option>').join("") + '</select></div><div class="product-field"><label for="productLanguages">Idiomas</label><input id="productLanguages" maxlength="120" value="' + esc(p.languages || "") + '" placeholder="Español, inglés B1…"></div><div class="product-field full"><label for="productInterests">Intereses</label><input id="productInterests" maxlength="180" value="' + esc(p.interests || "") + '" placeholder="Inclusión, fotografía, medio ambiente…"></div><div class="product-field full"><label for="productExperience">Experiencia que quieres destacar</label><textarea id="productExperience" maxlength="1000" placeholder="Voluntariado, estudios, proyectos personales…">' + esc(p.experience || "") + '</textarea></div><div class="product-field full"><label for="productStrengths">Qué puedes aportar a un grupo</label><textarea id="productStrengths" maxlength="700" placeholder="Escucha, creatividad, organización…">' + esc(p.strengths || "") + '</textarea></div></div><div class="privacy-note"><b>Privacidad:</b><span>El perfil se almacena en localStorage. Solo se enviará al asistente el texto que tú decidas usar.</span></div><div class="product-form-actions"><button class="product-button danger" id="clearProfile" type="button">Borrar perfil</button><button class="product-button primary" type="submit">Guardar perfil</button></div></form>';
    const modal = modalShell("profile", "Compatibilidad", "Mi perfil", body);
    modal.querySelector("#profileForm").onsubmit = event => {
      event.preventDefault(); const next = {age:modal.querySelector("#productAge").value,residence:modal.querySelector("#productResidence").value,type:modal.querySelector("#productType").value,languages:modal.querySelector("#productLanguages").value.trim(),interests:modal.querySelector("#productInterests").value.trim(),experience:modal.querySelector("#productExperience").value.trim(),strengths:modal.querySelector("#productStrengths").value.trim()};
      write(KEYS.profile, next); const age = document.getElementById("age"); if (age && next.age) { age.value = next.age; age.dispatchEvent(new Event("input", {bubbles:true})); } updateSummaries(); enhanceCards(); modal.close(); toast("Perfil guardado en este dispositivo");
    };
    modal.querySelector("#clearProfile").onclick = () => { localStorage.removeItem(KEYS.profile); updateSummaries(); enhanceCards(); modal.close(); toast("Perfil eliminado"); };
  }

  function addApplication(project) {
    const data = applications();
    if (!data[project.identifier]) data[project.identifier] = {status:"preparing", updated:new Date().toISOString(), note:""};
    write(KEYS.applications, data); beacon(project.identifier, "application"); updateSummaries(); toast("Añadida a Mis solicitudes");
  }
  function openApplications() {
    const data = applications(), ids = Object.keys(data);
    const rows = ids.map(id => { const project = byId(id); if (!project) return ""; const item = data[id]; return '<div class="application-row"><div><h3><a href="' + projectUrl(project) + '">' + esc(project.title) + '</a></h3><p>' + esc(COUNTRIES[project.country_code] || project.country_code || "") + ' · Límite ' + esc(fmt(project.application_deadline)) + '</p></div><select data-application-status="' + esc(id) + '" aria-label="Estado de ' + esc(project.title) + '">' + Object.keys(STATUS).map(value => '<option value="' + value + '"' + (item.status === value ? " selected" : "") + '>' + STATUS[value] + '</option>').join("") + '</select><button type="button" data-application-remove="' + esc(id) + '" aria-label="Quitar">×</button></div>'; }).join("");
    const modal = modalShell("applications", "Seguimiento", "Mis solicitudes", '<p class="product-intro">Actualiza el estado de cada candidatura. Este tablero es privado y permanece en este dispositivo.</p><div class="product-list">' + (rows || '<div class="product-empty">Todavía no sigues ninguna solicitud. Abre una oportunidad y pulsa “Preparar solicitud”.</div>') + '</div>');
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
    const project = byId(identifier) || catalog[0]; if (!project) return toast("No hay oportunidades disponibles"); const p = profile();
    const body = '<p class="product-intro">El asistente organiza únicamente los hechos que tú aportes. No debe inventar experiencia ni sustituir tu voz.</p><form id="assistantForm"><div class="product-grid"><div class="product-field full"><label for="assistantProject">Oportunidad</label><select id="assistantProject">' + projectOptions(project.identifier) + '</select></div><div class="product-field"><label for="assistantTask">Qué necesitas</label><select id="assistantTask"><option value="motivation">Explicar mi motivación</option><option value="why_me">Qué puedo aportar</option><option value="experience">Presentar mi experiencia</option><option value="review">Revisar mi borrador</option></select></div><div class="product-field"><label for="assistantMotivation">Motivación real</label><textarea id="assistantMotivation" placeholder="¿Por qué te interesa de verdad?"></textarea></div><div class="product-field full"><label for="assistantDraft">Borrador existente (opcional)</label><textarea id="assistantDraft" placeholder="Pega aquí la pregunta o tu texto"></textarea></div></div><div class="product-form-actions"><button class="product-button primary" id="assistantSubmit" type="submit">Crear borrador responsable</button></div></form><div id="assistantResult"></div>';
    const modal = modalShell("assistant", "Ayuda de redacción", "Preparar candidatura", body);
    modal.querySelector("#assistantForm").onsubmit = event => { event.preventDefault(); const button = modal.querySelector("#assistantSubmit"); button.disabled = true; button.textContent = "Preparando…"; const selected = modal.querySelector("#assistantProject").value; fetch("/api/application-assistant", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({identifier:selected,task:modal.querySelector("#assistantTask").value,draft:modal.querySelector("#assistantDraft").value,motivation:modal.querySelector("#assistantMotivation").value,experience:p.experience||"",strengths:p.strengths||"",languages:p.languages||""})}).then(response => { if (!response.ok) throw Error(); return response.json(); }).then(result => { modal.querySelector("#assistantResult").innerHTML = '<div class="assistant-output"><textarea id="assistantOutput">' + esc(result.draft || "") + '</textarea></div>'; const output = modal.querySelector(".assistant-output"); output.insertAdjacentHTML("beforeend", '<ul>' + (result.tips || []).map(tip => '<li>' + esc(tip) + '</li>').join("") + '</ul><p class="notice">' + esc(result.notice || "Revisa siempre el borrador antes de enviarlo.") + '</p><button class="product-button" id="copyAssistant" type="button">Copiar texto</button>'); output.querySelector("#copyAssistant").onclick = () => navigator.clipboard.writeText(modal.querySelector("#assistantOutput").value).then(() => toast("Borrador copiado")); beacon(selected, "assistant"); }).catch(() => { modal.querySelector("#assistantResult").innerHTML = '<div class="product-empty">El asistente no está disponible ahora. Conserva tu texto y prueba más tarde.</div>'; }).finally(() => { button.disabled = false; button.textContent = "Crear borrador responsable"; }); };
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
    card.insertAdjacentHTML("afterbegin", '<div class="project-eligibility ' + result.state + '"><strong>' + esc(result.label) + '</strong><br>' + esc(result.reasons.slice(0, 2).join(" · ")) + '</div>');
    card.insertAdjacentHTML("beforeend", '<div class="project-product-card"><h3>Prepara esta oportunidad</h3><div class="project-product-actions"><button type="button" data-product-action="application" data-id="' + esc(project.identifier) + '">Seguir solicitud</button><button type="button" data-product-action="assistant" data-id="' + esc(project.identifier) + '">Asistente</button><button type="button" data-product-action="documents" data-id="' + esc(project.identifier) + '">Documentos</button><button type="button" data-product-action="travel" data-id="' + esc(project.identifier) + '">Calcular viaje</button><button type="button" data-product-action="calendar" data-id="' + esc(project.identifier) + '">Calendario</button><button type="button" data-product-action="compare" data-id="' + esc(project.identifier) + '">Comparar</button></div><div class="trace-note"><i></i><span>' + esc(project.infopack_enriched ? "Ampliada desde el infopack oficial" : "Datos estructurados por Corradi") + ' · ' + esc(fmt((project.updated || project.created || "").slice(0,10))) + '</span></div></div>');
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
      if (opener) { event.preventDefault(); ({profile:openProfile,applications:openApplications,compare:openCompare,tools:openTools})[opener.dataset.productOpen](); return; }
      const action = event.target.closest("[data-product-action]");
      if (action) { event.preventDefault(); event.stopPropagation(); routeAction(action.dataset.productAction, action.dataset.id); return; }
      const clear = event.target.closest("[data-clear-filter]");
      if (clear) { const value = clear.dataset.clearFilter; ["search","type","country","age"].forEach(id => { if (value !== "all" && value !== id) return; const field = document.getElementById(id); if (field) { field.value = ""; field.dispatchEvent(new Event(id === "search" || id === "age" ? "input" : "change", {bubbles:true})); } }); updateFilterChips(); }
    }, true);
    ["search","type","country","age"].forEach(id => { const field = document.getElementById(id); if (field) field.addEventListener(id === "search" || id === "age" ? "input" : "change", () => setTimeout(updateFilterChips)); });
  }

  function initHome(data) {
    catalog = data.results || []; generated = data.generated || "";
    bindGlobal(); updateSummaries(); updateFilterChips(); enhanceCards(); enhanceDetail();
    const observer = new MutationObserver(() => { enhanceCards(); enhanceDetail(); updateFilterChips(); });
    ["allCards","urgentCards","weeklyTop","rowSoon","rowYE","rowTC","detail"].forEach(id => { const node = document.getElementById(id); if (node) observer.observe(node, {childList:true, subtree:true}); });
  }
  function initProject(data) {
    catalog = [data]; currentProject = data; bindGlobal(); updateSummaries();
    const apply = () => enhanceProjectPage(data); apply();
    const app = document.getElementById("app"); if (app) new MutationObserver(apply).observe(app, {childList:true, subtree:true});
  }

  const projectMatch = location.pathname.match(/^\/proyecto\/(CORRADI-\d{4}-\d{4})$/);
  const request = projectMatch ? fetch("/opportunities/" + encodeURIComponent(projectMatch[1])).then(r => r.ok ? r.json() : Promise.reject()) : fetch("/api/map").then(r => r.ok ? r.json() : Promise.reject());
  request.then(data => projectMatch ? initProject(data) : initHome(data)).catch(() => {});
})();
