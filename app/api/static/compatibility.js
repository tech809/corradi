(function (global) {
  "use strict";

  var KEY = "corradi-profile-v3", LEGACY_KEY = "corradi-profile-v2";
  var TAXONOMY = [
    {id:"nature", label:"Naturaleza y ecología", aliases:["naturaleza","nature","ecologia","ecology","biodiversidad","biodiversity","permacultura","permaculture","medio ambiente","environmental protection","conservacion","rural life","vida rural"]},
    {id:"outdoor", label:"Actividades al aire libre", aliases:["aire libre","outdoor","outdoors","outdoor learning","senderismo","hiking","aventura","adventure education","camping"]},
    {id:"sport", label:"Deporte y movimiento", aliases:["deporte","sports","sport","actividad fisica","physical activity","fitness","movimiento corporal","body movement","danza","dance","embodiment","conciencia corporal"]},
    {id:"sustainability", label:"Sostenibilidad y clima", aliases:["sostenibilidad","sustainability","sustainable development","cambio climatico","climate change","economia circular","circular economy","eco-friendly","green skills"]},
    {id:"facilitation", label:"Facilitación y dinámicas", aliases:["facilitacion","facilitation","facilitator","dinamicas de grupo","group dynamics","formacion de formadores","training of trainers","trainer skills","designing workshops"]},
    {id:"youthwork", label:"Youth work y educación no formal", aliases:["trabajo juvenil","trabajo con jovenes","youth work","youth worker","educacion no formal","non-formal education","aprendizaje no formal","experiential learning","aprendizaje experiencial"]},
    {id:"wellbeing", label:"Bienestar y salud mental", aliases:["bienestar","wellbeing","well-being","salud mental","mental health","mindfulness","resiliencia","resilience","inteligencia emocional","emotional intelligence"]},
    {id:"inclusion", label:"Inclusión y diversidad", aliases:["inclusion","diversidad","diversity","discapacidad","disability","accesibilidad","accessibility","igualdad de genero","gender equality","neurodiversidad"]},
    {id:"participation", label:"Participación y democracia", aliases:["participacion juvenil","youth participation","democracia","democracy","ciudadania activa","active citizenship","compromiso civico","civic engagement","politicas juveniles"]},
    {id:"rights", label:"Derechos humanos y justicia social", aliases:["derechos humanos","human rights","justicia social","social justice","construccion de paz","peacebuilding","migracion","migration","antidiscriminacion","no discriminacion"]},
    {id:"digital", label:"Digital, medios e IA", aliases:["digital","inteligencia artificial","artificial intelligence","fake news","desinformacion","disinformation","alfabetizacion mediatica","media literacy","redes sociales","social media","gamificacion","gamification"]},
    {id:"creative", label:"Creatividad, arte y comunicación", aliases:["creatividad","creativity","arte","arts","teatro","theatre","fotografia","photography","storytelling","musica","music","audiovisual","comunicacion"]},
    {id:"leadership", label:"Liderazgo y desarrollo personal", aliases:["liderazgo","leadership","desarrollo personal","personal development","autoconocimiento","self-awareness","empoderamiento","empowerment","habilidades sociales","social skills"]},
    {id:"projects", label:"Proyectos y emprendimiento", aliases:["gestion de proyectos","project management","desarrollo de proyectos","project development","emprendimiento","entrepreneurship","emprendimiento social","social entrepreneurship","erasmus+ ka2"]},
    {id:"community", label:"Voluntariado y comunidad", aliases:["voluntariado","volunteering","volunteer","comunidad","community building","solidaridad","solidarity","asociacionismo","cuerpo europeo de solidaridad","european solidarity corps"]},
    {id:"intercultural", label:"Interculturalidad e idiomas", aliases:["interculturalidad","intercultural learning","dialogo intercultural","intercultural dialogue","multicultural","ingles","english language","language learning"]}
  ];

  function fold(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
  function containsPhrase(text, phrase) {
    var hay = " " + fold(text).replace(/[^a-z0-9+]+/g, " ").trim() + " ";
    var needle = " " + fold(phrase).replace(/[^a-z0-9+]+/g, " ").trim() + " ";
    return needle.trim() && hay.indexOf(needle) >= 0;
  }
  function conceptById(id) { return TAXONOMY.filter(function (item) { return item.id === id; })[0]; }
  function cleanPriorities(value) {
    var out = {}, allowed = ["required","positive","avoid"];
    if (!value || typeof value !== "object") return out;
    TAXONOMY.forEach(function (concept) { if (allowed.indexOf(value[concept.id]) >= 0) out[concept.id] = value[concept.id]; });
    return out;
  }
  function migrateInterests(interests) {
    var out = {};
    TAXONOMY.forEach(function (concept) {
      if (concept.aliases.some(function (alias) { return containsPhrase(interests, alias); })) out[concept.id] = "positive";
    });
    return out;
  }
  function readProfile() {
    var raw = {}, legacy = false;
    try {
      var current = localStorage.getItem(KEY);
      legacy = !current;
      raw = JSON.parse(current || localStorage.getItem(LEGACY_KEY) || "{}") || {};
    } catch (_) {}
    var priorities = cleanPriorities(raw.priorities);
    if (!Object.keys(priorities).length && raw.interests) priorities = migrateInterests(raw.interests);
    // Corradi es solo para residentes en España: la residencia ya no se pregunta.
    // Formatos: ahora se pueden elegir varios (`types`). `type` se mantiene como el único
    // formato elegido (o "" si hay varios/ninguno) para las pantallas que aún usan un select.
    var TYPE_IDS = ["YOUTH_EXCHANGE","TRAINING_COURSE","VOLUNTEERING"];
    var types = (Array.isArray(raw.types) ? raw.types : (raw.type ? [raw.type] : [])).filter(function (t, i, all) { return TYPE_IDS.indexOf(t) >= 0 && all.indexOf(t) === i; });
    if (types.length === TYPE_IDS.length) types = [];
    var safe = {age:raw.age || "", residence:"ES", type:types.length === 1 ? types[0] : "", types:types, priorities:priorities, requiredText:typeof raw.requiredText === "string" ? raw.requiredText.slice(0, 140) : ""};
    if (legacy || raw.interests || Object.keys(raw).some(function (key) { return ["age","residence","type","types","priorities","requiredText"].indexOf(key) < 0; })) {
      localStorage.setItem(KEY, JSON.stringify(safe));
      if (legacy) localStorage.removeItem(LEGACY_KEY);
    }
    return safe;
  }
  function projectText(project) {
    return [project.title,project.topic,project.summary,project.detailed_description,project.learning_outcomes,project.participant_profile,project.programme_details].join(" ");
  }
  // Campos de la "ficha extendida" (lo que viene del infopack o de la estructuración propia de
  // Corradi), no el resumen corto de la tarjeta: aquí es donde comprobamos lo "imprescindible" en
  // texto libre, para no dar por bueno algo que solo aparece de pasada en el título.
  var EXTENDED_FIELDS = ["detailed_description","programme_details","learning_outcomes","participant_profile","accommodation_details","covered_costs","travel_details","eligibility_countries","contact_information"];
  function extendedText(project) { return EXTENDED_FIELDS.map(function (field) { return project[field] || ""; }).join(" "); }
  function parseRequiredText(raw) { return String(raw || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 6); }
  function conceptMatch(project, concept) {
    var topic = project.topic || "", core = [project.title,project.learning_outcomes].join(" "), body = projectText(project);
    var inTopic = concept.aliases.some(function (alias) { return containsPhrase(topic, alias); });
    var inCore = inTopic || concept.aliases.some(function (alias) { return containsPhrase(core, alias); });
    var inBody = inCore || concept.aliases.some(function (alias) { return containsPhrase(body, alias); });
    return {matched:inBody, central:inCore, source:inTopic ? "topic" : inCore ? "core" : inBody ? "description" : null};
  }
  function listLabels(ids) { return ids.map(function (id) { var item=conceptById(id); return item ? item.label.toLowerCase() : id; }); }
  // Cache por perfil: discover.html/mapa.html llaman a evaluate() del mismo proyecto muchas
  // veces por segundo (cada tecla en el buscador, cada MutationObserver) con el MISMO perfil
  // sin cambiar; sin esto se repite todo el matching de texto en cada pasada, notable en móvil
  // con el catálogo entero + las filas de colecthemas. Se invalida sola si cambia el perfil.
  var _cache = {sig: null, map: null};
  function profileSignature(data) {
    return (data.age || "") + "|" + (data.residence || "") + "|" + (data.types || [data.type]).join(",") + "|" + JSON.stringify(data.priorities || {}) + "|" + (data.requiredText || "");
  }
  function evaluate(project, supplied) {
    if (supplied) return computeEvaluate(project, supplied);
    var data = readProfile(), sig = profileSignature(data);
    if (_cache.sig !== sig) { _cache.sig = sig; _cache.map = new Map(); }
    var cached = _cache.map.get(project.identifier);
    if (cached) return cached;
    var result = computeEvaluate(project, data);
    _cache.map.set(project.identifier, result);
    return result;
  }
  function computeEvaluate(project, data) {
    var reasons = [], age = Number(data.age || 0), codes = Array.isArray(project.eligibility_country_codes) ? project.eligibility_country_codes : [];
    if (!age || !data.residence) return {score:null,state:"unknown",label:"Configura tu perfil",confidence:"baja",reasons:["Añade edad y residencia para comprobar requisitos"]};
    if (!codes.length) return {score:null,state:"warn",label:"Revisa requisitos",confidence:"baja",reasons:["La fuente no publica una lista de países verificable"]};
    if (codes.indexOf(data.residence) < 0) {
      // Sin el infopack real procesado, la lista de países puede venir solo del país de
      // destino (lo único que menciona el resumen), no de los países realmente admitidos —
      // pasó con un curso en Turquía que en teoría también admitía España. No lo tratamos
      // como un "no" verificado hasta que el infopack confirme la lista completa.
      if (!project.infopack_enriched) return {score:null,state:"warn",label:"Revisa requisitos",confidence:"baja",reasons:["Aún no hemos confirmado todos los países admitidos"]};
      return {score:0,state:"no",label:"Revisa requisitos",confidence:"alta",reasons:["España no figura entre los países admitidos"]};
    }
    reasons.push("España figura entre los países admitidos");
    var min = Number(project.participant_min_age || 0), max = Number(project.participant_max_age || 0);
    if ((min && age < min) || (max && age > max)) return {score:0,state:"no",label:"Revisa requisitos",confidence:"alta",reasons:["Tu edad no entra en el rango publicado"]};
    reasons.push(min || max ? "Tu edad encaja" : "La convocatoria no concreta el rango de edad");

    var priorities = cleanPriorities(data.priorities), selected = Object.keys(priorities), requiredKeywords = parseRequiredText(data.requiredText);
    if (!selected.length && !requiredKeywords.length) return {score:null,state:"unknown",label:"Añade preferencias",confidence:"media",reasons:reasons.concat(["Elige temas muy importantes, interesantes o que prefieres evitar"])};
    // Afinidad = qué parte de lo que pides cubre la oportunidad (0–100), no una base fija
    // con sumas. Cada tema pesa según DÓNDE aparece: en el tema principal cuenta entero,
    // en título/objetivos un 60 %, y si solo sale de pasada en la descripción, un 25 %.
    // El formato no suma: ya actúa como filtro y sumarlo inflaba todas las notas por igual.
    var wantedTypes = Array.isArray(data.types) ? data.types : (data.type ? [data.type] : []);
    if (wantedTypes.length) {
      var typeMatch = wantedTypes.indexOf(project.type) >= 0 || (wantedTypes.indexOf("VOLUNTEERING") >= 0 && project.type === "ESC");
      reasons.push(typeMatch ? "Coincide con tu formato preferido" : "No es tu formato preferido");
    }
    var EVIDENCE = {topic:1, core:.6, description:.25};
    var matchedRequired=[], missingRequired=[], matchedPositive=[], weakPositive=[], matchedAvoid=[], topicEvidence=0;
    var earned = 0, possible = 0;
    selected.forEach(function (id) {
      var match=conceptMatch(project,conceptById(id)), mode=priorities[id], weight=match.source ? EVIDENCE[match.source] : 0;
      if (match.source === "topic") topicEvidence++;
      if (mode === "required") {
        possible += 2; earned += 2 * weight;
        (match.central ? matchedRequired : missingRequired).push(id);
      } else if (mode === "positive") {
        possible += 1; earned += weight;
        if (match.central) matchedPositive.push(id); else if (match.matched) weakPositive.push(id);
      } else if (mode === "avoid" && match.central) matchedAvoid.push(id);
    });

    var extended = extendedText(project), hasExtended = extended.trim().length > 40;
    var matchedKeywords=[], missingKeywords=[], unverifiedKeywords=[];
    requiredKeywords.forEach(function (keyword) {
      possible += 2;
      if (containsPhrase(extended, keyword)) { matchedKeywords.push(keyword); earned += 2; }
      else if (hasExtended) missingKeywords.push(keyword);
      else { unverifiedKeywords.push(keyword); earned += .5; }
    });

    // Solo "evitar" marcado: no hay nada que cubrir, partimos de encaje completo y restamos.
    var score = possible ? Math.round(100 * earned / possible) : 100;
    score -= matchedAvoid.length * 30;
    if (missingRequired.length || missingKeywords.length) score = Math.min(score, 40);
    // Ficha pobre = sin infopack procesado Y sin descripción larga (los ESC oficiales del
    // Portal Europeo de la Juventud traen la descripción completa aunque no haya infopack).
    var incomplete = !project.infopack_enriched && String(project.detailed_description || "").length < 300;
    if (incomplete) score = Math.min(score, 70);
    score = Math.max(5, Math.min(100, score));

    var positiveTotal = selected.filter(function (id) { return priorities[id] === "positive"; }).length;
    if (positiveTotal) reasons.push("Cubre " + (matchedPositive.length + weakPositive.length) + " de tus " + positiveTotal + " temas");
    if (matchedRequired.length) reasons.push("Muy importantes presentes: " + listLabels(matchedRequired).join(", "));
    if (missingRequired.length) reasons.push("Falta algo muy importante: " + listLabels(missingRequired).join(", "));
    if (matchedPositive.length) reasons.push("Es tema central: " + listLabels(matchedPositive).join(", "));
    if (weakPositive.length) reasons.push("Solo se menciona de pasada: " + listLabels(weakPositive).join(", "));
    if (matchedAvoid.length) reasons.push("Incluye algo que prefieres evitar: " + listLabels(matchedAvoid).join(", "));
    if (matchedKeywords.length) reasons.push("Incluye lo que buscas: " + matchedKeywords.join(", "));
    if (missingKeywords.length) reasons.push("No parece incluir: " + missingKeywords.join(", "));
    if (unverifiedKeywords.length) reasons.push("Ficha poco detallada, no podemos confirmar: " + unverifiedKeywords.join(", "));
    if (incomplete) reasons.push("Ficha con poca información: la afinidad no pasa del 70 %");

    var confidence = incomplete ? "baja" : project.topic && project.participant_profile && project.detailed_description ? (topicEvidence ? "alta" : "media") : "media";
    var isYes = score >= 75 && !missingRequired.length && !matchedAvoid.length && !missingKeywords.length;
    return {score:score,state:isYes ? "yes" : "warn",label:score + "% afinidad",confidence:confidence,incomplete:incomplete,reasons:reasons,matchedRequired:matchedRequired,missingRequired:missingRequired,matchedPositive:matchedPositive,weakPositive:weakPositive,matchedAvoid:matchedAvoid,missingKeywords:missingKeywords};
  }
  global.CorradiCompatibility = {readProfile:readProfile,evaluate:evaluate,key:KEY,taxonomy:TAXONOMY,cleanPriorities:cleanPriorities};
})(window);
