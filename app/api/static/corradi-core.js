// Utilidades compartidas por la home, las fichas y el mapa. Antes cada página tenía su propia
// copia de estas funciones y listas (y la de países había divergido: unas páginas mostraban
// el código "MK" donde otras decían "Macedonia del Norte").
(function (global) {
  "use strict";

  var COUNTRIES = {AL:"Albania",DE:"Alemania",AM:"Armenia",AT:"Austria",AZ:"Azerbaiyán",BA:"Bosnia y Herzegovina",BG:"Bulgaria",BE:"Bélgica",CZ:"Chequia",CY:"Chipre",HR:"Croacia",DK:"Dinamarca",SK:"Eslovaquia",SI:"Eslovenia",ES:"España",EE:"Estonia",FI:"Finlandia",FR:"Francia",GE:"Georgia",GR:"Grecia",HU:"Hungría",IE:"Irlanda",IS:"Islandia",IT:"Italia",XK:"Kosovo",LV:"Letonia",LI:"Liechtenstein",LT:"Lituania",LU:"Luxemburgo",MK:"Macedonia del Norte",MT:"Malta",MD:"Moldavia",ME:"Montenegro",NO:"Noruega",NL:"Países Bajos",PL:"Polonia",PT:"Portugal",GB:"Reino Unido",RO:"Rumanía",RS:"Serbia",SE:"Suecia",CH:"Suiza",TR:"Turquía",UA:"Ucrania"};

  // Formatos: nombre largo y abreviatura usada en chips y resúmenes.
  var TYPES = {
    YOUTH_EXCHANGE: {label: "Youth Exchange", short: "YE"},
    TRAINING_COURSE: {label: "Training Course", short: "TC"},
    VOLUNTEERING: {label: "Voluntariado ESC", short: "ESC"}
  };

  var ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
  function esc(value) { return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) { return ESCAPES[ch]; }); }
  function flag(code) {
    return code && /^[A-Z]{2}$/i.test(code) ? String.fromCodePoint.apply(null, code.toUpperCase().split("").map(function (ch) { return 127397 + ch.charCodeAt(0); })) : "";
  }
  function countryName(code) { return COUNTRIES[code] || code || ""; }
  function typeLabel(type) { return (TYPES[type] || TYPES[type === "ESC" ? "VOLUNTEERING" : ""] || {label: type || ""}).label; }
  function typeShort(type) { return (TYPES[type] || TYPES[type === "ESC" ? "VOLUNTEERING" : ""] || {short: type || ""}).short; }
  function daysLeft(isoDate) {
    if (!isoDate) return null;
    return Math.ceil((new Date(String(isoDate).slice(0, 10) + "T23:59:59") - new Date()) / 86400000);
  }
  function deadlineLabel(days) {
    if (days == null) return "Sin fecha límite";
    if (days <= 0) return "Cierra hoy";
    if (days === 1) return "Cierra mañana";
    return "Cierra en " + days + " días";
  }

  // Catálogo abierto (/api/map) pedido UNA vez por página: antes la home lo descargaba dos
  // veces (el listado y el script de compatibilidad hacían cada uno su propio fetch).
  var catalogPromise = null;
  function catalog() {
    if (!catalogPromise) {
      catalogPromise = fetch("/api/map", {headers: {Accept: "application/json"}}).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
      catalogPromise.catch(function () { catalogPromise = null; });
    }
    return catalogPromise;
  }

  global.Corradi = {catalog: catalog, COUNTRIES: COUNTRIES, TYPES: TYPES, esc: esc, flag: flag, countryName: countryName, typeLabel: typeLabel, typeShort: typeShort, daysLeft: daysLeft, deadlineLabel: deadlineLabel};
})(window);
