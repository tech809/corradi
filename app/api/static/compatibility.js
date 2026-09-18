(function (global) {
  "use strict";
  var KEY = "corradi-profile-v2";
  function readProfile() {
    var raw = {};
    try { raw = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (_) {}
    var safe = {age:raw.age || "", residence:raw.residence || "", type:raw.type || "", interests:raw.interests || ""};
    if (Object.keys(raw).some(function (key) { return ["age","residence","type","interests"].indexOf(key) < 0; })) {
      localStorage.setItem(KEY, JSON.stringify(safe));
    }
    return safe;
  }
  function fold(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
  function evaluate(project, supplied) {
    var data = supplied || readProfile(), reasons = [], age = Number(data.age || 0), codes = Array.isArray(project.eligibility_country_codes) ? project.eligibility_country_codes : [];
    if (!age || !data.residence) return {score:null,state:"unknown",label:"Configura tu perfil",reasons:["Añade edad y residencia para comprobar requisitos"]};
    if (!codes.length) return {score:null,state:"warn",label:"Revisa requisitos",reasons:["La fuente no publica una lista de países verificable"]};
    if (codes.indexOf(data.residence) < 0) return {score:0,state:"no",label:"Revisa requisitos",reasons:["Tu país no figura entre los admitidos"]};
    reasons.push("Tu país figura en la convocatoria");
    var min = Number(project.participant_min_age || 0), max = Number(project.participant_max_age || 0);
    if ((min && age < min) || (max && age > max)) return {score:0,state:"no",label:"Revisa requisitos",reasons:["Tu edad no entra en el rango publicado"]};
    var score = 35;
    if (min || max) { score += 30; reasons.push("Tu edad encaja"); }
    else { score += 15; reasons.push("La convocatoria no concreta el rango de edad"); }
    if (data.type) {
      var typeMatch = data.type === project.type || (data.type === "VOLUNTEERING" && project.type === "ESC");
      if (typeMatch) { score += 15; reasons.push("Coincide con el formato que buscas"); }
      else reasons.push("Es un formato distinto de tu preferencia");
    }
    var interests = fold(data.interests).split(/[,;]+|\s+/).filter(function (word) { return word.length > 3; });
    if (interests.length) {
      var hay = fold([project.title, project.topic, project.summary, project.detailed_description, project.learning_outcomes].join(" "));
      var unique = interests.filter(function (word, index) { return interests.indexOf(word) === index && hay.indexOf(word) >= 0; });
      var denominator = Math.min(3, interests.length), interestPoints = Math.round(20 * Math.min(3, unique.length) / denominator);
      score += interestPoints;
      reasons.push(unique.length ? "Coincide con " + unique.slice(0, 3).join(", ") : "No detectamos coincidencias claras con tus intereses");
    }
    score = Math.max(0, Math.min(100, score));
    return {score:score,state:score >= 80 ? "yes" : "warn",label:score + "% compatible",reasons:reasons};
  }
  global.CorradiCompatibility = {readProfile:readProfile,evaluate:evaluate,key:KEY};
})(window);
