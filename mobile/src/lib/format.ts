import { TYPE_EXPLAINERS, TYPE_LABELS, TYPE_SHORT_LABELS, type Opportunity, type OpportunityType } from './types';

export { TYPE_EXPLAINERS, TYPE_LABELS, TYPE_SHORT_LABELS };

/**
 * Textos y fechas para pantallas y tarjetas. Formato a mano (sin Intl) para que
 * salga igual en iOS y Android sea cual sea el idioma del sistema.
 */

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];
const MONTHS_LONG = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

/**
 * Días para "Cierran pronto" (filtro de Explorar) y el tono `soon` del plazo.
 * OJO: NO decide "Última llamada"; eso es solo `isLastCall()` (marca `last_minute` de la web).
 */
export const CLOSING_SOON_DAYS = 7;
/** @deprecated Nombre antiguo de `CLOSING_SOON_DAYS` (no tiene que ver con "Última llamada"). */
export const LAST_CALL_DAYS = CLOSING_SOON_DAYS;

// ---------- Tipo ----------

export function typeLabel(type: OpportunityType | null | undefined): string {
  return type ? TYPE_LABELS[type] : 'Oportunidad Erasmus+';
}

/** Etiqueta corta para chips y filtros: "Intercambio", "Curso", "Voluntariado". */
export function typeShortLabel(type: OpportunityType | null | undefined): string {
  return type ? TYPE_SHORT_LABELS[type] : 'Erasmus+';
}

/** Explicación del formato (para el "¿qué es esto?" del chip de tipo) o null. */
export function typeExplainer(type: OpportunityType | null | undefined): string | null {
  return type ? TYPE_EXPLAINERS[type] : null;
}

/**
 * A quién va dirigido. Los cursos de formación son para quien trabaja con jóvenes; el resto,
 * por edad: "Jóvenes de 18 a 30 años", "Desde 18 años", "Hasta 30 años" o null si no hay dato.
 */
export function audienceText(
  o: Pick<Opportunity, 'type' | 'participant_min_age' | 'participant_max_age'>,
): string | null {
  if (o.type === 'TRAINING_COURSE') {
    return 'Pensado para quien trabaja con jóvenes (monitores, educadores, voluntarios de asociaciones)';
  }
  const min = o.participant_min_age;
  const max = o.participant_max_age;
  if (min && max) return min === max ? `Jóvenes de ${min} años` : `Jóvenes de ${min} a ${max} años`;
  if (min) return `Desde ${min} años`;
  if (max) return `Hasta ${max} años`;
  return null;
}

// ---------- País ----------

/** Nombre en español + nombre en inglés (para limpiar "Kaunas, Lithuania"). */
const COUNTRIES: Record<string, [string, string]> = {
  AL: ['Albania', 'Albania'], AM: ['Armenia', 'Armenia'], AT: ['Austria', 'Austria'],
  AZ: ['Azerbaiyán', 'Azerbaijan'], BA: ['Bosnia y Herzegovina', 'Bosnia and Herzegovina'],
  BE: ['Bélgica', 'Belgium'], BG: ['Bulgaria', 'Bulgaria'], BY: ['Bielorrusia', 'Belarus'],
  CH: ['Suiza', 'Switzerland'], CY: ['Chipre', 'Cyprus'], CZ: ['Chequia', 'Czech Republic'],
  DE: ['Alemania', 'Germany'], DK: ['Dinamarca', 'Denmark'], EE: ['Estonia', 'Estonia'],
  EG: ['Egipto', 'Egypt'], ES: ['España', 'Spain'], FI: ['Finlandia', 'Finland'],
  FR: ['Francia', 'France'], GB: ['Reino Unido', 'United Kingdom'], GE: ['Georgia', 'Georgia'],
  GR: ['Grecia', 'Greece'], HR: ['Croacia', 'Croatia'], HU: ['Hungría', 'Hungary'],
  IE: ['Irlanda', 'Ireland'], IS: ['Islandia', 'Iceland'], IT: ['Italia', 'Italy'],
  LI: ['Liechtenstein', 'Liechtenstein'], LT: ['Lituania', 'Lithuania'], LU: ['Luxemburgo', 'Luxembourg'],
  LV: ['Letonia', 'Latvia'], MA: ['Marruecos', 'Morocco'], MD: ['Moldavia', 'Moldova'],
  ME: ['Montenegro', 'Montenegro'], MK: ['Macedonia del Norte', 'North Macedonia'], MT: ['Malta', 'Malta'],
  NL: ['Países Bajos', 'Netherlands'], NO: ['Noruega', 'Norway'], PL: ['Polonia', 'Poland'],
  PT: ['Portugal', 'Portugal'], RO: ['Rumanía', 'Romania'], RS: ['Serbia', 'Serbia'],
  SE: ['Suecia', 'Sweden'], SI: ['Eslovenia', 'Slovenia'], SK: ['Eslovaquia', 'Slovakia'],
  TN: ['Túnez', 'Tunisia'], TR: ['Turquía', 'Turkey'], UA: ['Ucrania', 'Ukraine'],
  XK: ['Kosovo', 'Kosovo'],
};

/** La UE usa EL para Grecia y UK para Reino Unido; ISO usa GR y GB. */
function isoCode(code: string | null | undefined): string | null {
  if (!code) return null;
  const c = code.trim().toUpperCase();
  if (c === 'EL') return 'GR';
  if (c === 'UK') return 'GB';
  return /^[A-Z]{2}$/.test(c) ? c : null;
}

/** Bandera emoji a partir del código de país ("DE" → 🇩🇪). Cadena vacía si no hay código válido. */
export function flagEmoji(countryCode: string | null | undefined): string {
  const c = isoCode(countryCode);
  if (!c) return '';
  return String.fromCodePoint(...[...c].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65));
}

export function countryName(countryCode: string | null | undefined): string | null {
  const c = isoCode(countryCode);
  if (!c) return null;
  return COUNTRIES[c]?.[0] ?? c;
}

/**
 * "Herrnhut-Ruppersdorf, DE" → "Herrnhut-Ruppersdorf, Alemania";
 * "Kaunas, Lithuania" → "Kaunas, Lituania".
 */
export function placeLabel(o: Pick<Opportunity, 'location' | 'country_code'>): string | null {
  const c = isoCode(o.country_code);
  const country = countryName(o.country_code);
  const parts = (o.location ?? '').split(',').map((p) => p.trim()).filter(Boolean);
  const last = parts.at(-1)?.toLowerCase();
  const names = [o.country_code, c, ...(c && COUNTRIES[c] ? COUNTRIES[c] : [])]
    .filter(Boolean)
    .map((n) => String(n).toLowerCase());
  if (last && names.includes(last)) parts.pop();
  if (country) parts.push(country);
  return parts.length ? parts.join(', ') : null;
}

/**
 * Solo la ciudad/zona, sin el país: "Kaunas, Lithuania" → "Kaunas". null si no hay.
 * (Para cuando el país ya se ve en otro sitio, p. ej. en la portada.)
 */
export function cityLabel(o: Pick<Opportunity, 'location' | 'country_code'>): string | null {
  const c = isoCode(o.country_code);
  const parts = (o.location ?? '').split(',').map((p) => p.trim()).filter(Boolean);
  const names = new Set(
    [o.country_code, c, ...(c && COUNTRIES[c] ? COUNTRIES[c] : [])].filter(Boolean).map((n) => String(n).toLowerCase()),
  );
  const kept = parts.filter((p) => !names.has(p.toLowerCase()));
  return kept.length ? kept.join(', ') : null;
}

// ---------- Fotos ----------

/** Fotos de la web para proyectos sin `image_url` (app/api/static/mapa.html, `IMAGE_POOL`). */
export const PHOTO_POOL_SIZE = 40;
const PHOTO_POOL_BASE = 'https://mapa.proactivefuture.eu/assets/pool/';

/** Mismo hash que la web (`_hashId`): h = h * 31 + código, sin signo de 32 bits. */
export function photoPoolIndex(key: string | null | undefined): number {
  const s = String(key ?? '');
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % PHOTO_POOL_SIZE;
}

/** Foto de la colección de la web para este proyecto (la misma que enseña el mapa web). */
export function poolImageUrl(o: Pick<Opportunity, 'identifier'> & { title?: string | null }): string {
  const n = photoPoolIndex(o.identifier || o.title) + 1;
  return `${PHOTO_POOL_BASE}${n < 10 ? `0${n}` : n}.jpg`;
}

/** Foto de portada: la del proyecto o, si no tiene, la de la colección (como `mapImage` de la web). */
export function coverImageUrl(o: Pick<Opportunity, 'identifier' | 'image_url'> & { title?: string | null }): string {
  return o.image_url || poolImageUrl(o);
}

// ---------- Fechas ----------

/** "2026-11-15" (o ISO con hora) → fecha local a mediodía, o null si no se entiende. */
export function parseDay(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12);
}

/** "15 nov 2026"; sin año si es el año en curso y `omitCurrentYear`. */
export function formatDate(iso: string | null | undefined, omitCurrentYear = false): string | null {
  const d = parseDay(iso);
  if (!d) return null;
  const base = `${d.getDate()} ${MONTHS[d.getMonth()]}`;
  return omitCurrentYear && d.getFullYear() === new Date().getFullYear() ? base : `${base} ${d.getFullYear()}`;
}

/** "15 de noviembre de 2026". */
export function formatDateLong(iso: string | null | undefined): string | null {
  const d = parseDay(iso);
  if (!d) return null;
  return `${d.getDate()} de ${MONTHS_LONG[d.getMonth()]} de ${d.getFullYear()}`;
}

/** "23–31 ene 2027", "30 nov – 8 dic", "15 nov 2026 – 14 nov 2027". */
export function formatDateRange(start: string | null | undefined, end: string | null | undefined): string | null {
  const s = parseDay(start);
  const e = parseDay(end);
  if (!s && !e) return null;
  if (!s) return `Hasta el ${formatDate(end, true)}`;
  if (!e) return `Desde el ${formatDate(start, true)}`;
  const thisYear = new Date().getFullYear();
  const sameYear = s.getFullYear() === e.getFullYear();
  const endYear = sameYear && e.getFullYear() === thisYear ? '' : ` ${e.getFullYear()}`;
  if (sameYear && s.getMonth() === e.getMonth()) {
    if (s.getDate() === e.getDate()) return `${s.getDate()} ${MONTHS[s.getMonth()]}${endYear}`;
    return `${s.getDate()}–${e.getDate()} ${MONTHS[e.getMonth()]}${endYear}`;
  }
  const startText = `${s.getDate()} ${MONTHS[s.getMonth()]}${sameYear ? '' : ` ${s.getFullYear()}`}`;
  return `${startText} – ${e.getDate()} ${MONTHS[e.getMonth()]}${endYear}`;
}

/** Días naturales desde hoy hasta la fecha (0 = hoy, negativo = ya pasó). */
export function daysUntil(iso: string | null | undefined, now: Date = new Date()): number | null {
  const d = parseDay(iso);
  if (!d) return null;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
  return Math.round((d.getTime() - today.getTime()) / 86_400_000);
}

/** "Hoy", "Ayer", "Hace 3 días"… para el alta en Corradi (`created`). */
export function relativeAdded(iso: string | null | undefined): string | null {
  const days = daysUntil(iso);
  if (days == null) return null;
  const ago = -days;
  if (ago <= 0) return 'Hoy';
  if (ago === 1) return 'Ayer';
  if (ago < 7) return `Hace ${ago} días`;
  return `El ${formatDate(iso, true)}`;
}

// ---------- Plazo ----------

export type DeadlineTone = 'closed' | 'urgent' | 'soon' | 'normal' | 'unknown';

export interface DeadlineInfo {
  text: string; // "Cierra en 3 días", "Plazo estimado: 20 nov"…
  tone: DeadlineTone;
  days: number | null;
  estimated: boolean;
}

export function isClosed(o: Pick<Opportunity, 'status' | 'application_deadline'>): boolean {
  if (o.status && o.status !== 'open') return true;
  const days = daysUntil(o.application_deadline);
  return days != null && days < 0;
}

export function deadlineInfo(o: Pick<Opportunity, 'status' | 'application_deadline' | 'deadline_estimated'>): DeadlineInfo {
  const days = daysUntil(o.application_deadline);
  const estimated = !!o.deadline_estimated;
  if (isClosed(o)) return { text: 'Plazo cerrado', tone: 'closed', days, estimated };
  if (days == null) return { text: 'Plazo sin confirmar', tone: 'unknown', days, estimated };
  const tone: DeadlineTone = days <= 3 ? 'urgent' : days <= CLOSING_SOON_DAYS ? 'soon' : 'normal';
  if (estimated) return { text: `Plazo estimado: ${formatDate(o.application_deadline, true)}`, tone, days, estimated };
  return { text: deadlineRelative(days, o.application_deadline), tone, days, estimated };
}

function deadlineRelative(days: number, iso: string | null): string {
  if (days === 0) return 'Cierra hoy';
  if (days === 1) return 'Cierra mañana';
  if (days <= 30) return `Cierra en ${days} días`;
  return `Cierra el ${formatDate(iso, true)}`;
}

/** Atajo: solo el texto del plazo. */
export function deadlineText(o: Pick<Opportunity, 'status' | 'application_deadline' | 'deadline_estimated'>): string {
  return deadlineInfo(o).text;
}

/**
 * "Última llamada": ÚNICO criterio en toda la app (tarjetas, ficha, lector de pantalla), igual que
 * la web: abierto y marcado `last_minute` (el mensaje original pedía gente con urgencia).
 * La cercanía del plazo NO es "Última llamada": se cuenta solo con el texto/color del plazo.
 */
export function isLastCall(o: Pick<Opportunity, 'status' | 'application_deadline' | 'last_minute'>): boolean {
  return !isClosed(o) && Boolean(o.last_minute);
}

// ---------- Otros datos ----------

/** "18–30 años", "Desde 18 años", "Hasta 30 años" o null. */
export function ageText(o: Pick<Opportunity, 'participant_min_age' | 'participant_max_age'>): string | null {
  const min = o.participant_min_age;
  const max = o.participant_max_age;
  if (min && max) return min === max ? `${min} años` : `${min}–${max} años`;
  if (min) return `Desde ${min} años`;
  if (max) return `Hasta ${max} años`;
  return null;
}

/** La API manda `cost` como número (0 = sin cuota) aunque a veces es texto. */
export function costText(cost: unknown): string | null {
  if (cost == null || cost === '') return null;
  const n = typeof cost === 'number' ? cost : Number(String(cost).replace(',', '.'));
  if (Number.isFinite(n)) return n === 0 ? 'Sin cuota de participación' : `Cuota de ${formatNumber(n)} €`;
  return String(cost).trim() || null;
}

/** Duración: "6 meses" (desde 2 meses, redondeado), "1,8 meses", "9 días". */
export function durationText(o: Pick<Opportunity, 'duration_months' | 'start_date' | 'end_date'>): string | null {
  let n = o.duration_months == null ? null : Number(o.duration_months);
  if (n == null || !Number.isFinite(n)) {
    const s = parseDay(o.start_date);
    const e = parseDay(o.end_date);
    if (!s || !e) return null;
    const days = Math.round((e.getTime() - s.getTime()) / 86_400_000) + 1;
    if (days < 1) return null;
    if (days < 28) return `${days} ${days === 1 ? 'día' : 'días'}`;
    n = days / 30.44;
  }
  if (n <= 0) return null;
  if (n >= 2) return `${Math.round(n)} meses`;
  const v = Math.round(n * 10) / 10;
  return `${formatNumber(v)} ${Math.abs(v - 1) < 0.05 ? 'mes' : 'meses'}`;
}

/** "sostenibilidad, inclusión social" → ["sostenibilidad", "inclusión social"] (sin números sueltos). */
export function topicList(topic: string | null | undefined): string[] {
  return (topic ?? '')
    .split(/\s*,\s*/)
    .map((t) => t.trim())
    .filter((t) => t && !/^\d+$/.test(t));
}

/** "4 proyectos nuevos" / "1 proyecto nuevo". */
export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/**
 * Número con formato es-ES hecho a mano (sin Intl): coma decimal y punto de miles a partir
 * de 10 000, como hace es-ES ("1200", "12.000", "3,5").
 */
export function formatNumber(n: number): string {
  const neg = n < 0;
  const [int, dec] = String(Math.abs(n)).split('.');
  const grouped = int.length > 4 ? int.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : int;
  return `${neg ? '-' : ''}${grouped}${dec ? `,${dec}` : ''}`;
}

/** "AT, BG, ES" → "Austria, Bulgaria, España"; si no son códigos, el texto tal cual. */
export function countryListText(text: string | null | undefined): string | null {
  const raw = (text ?? '').trim();
  if (!raw) return null;
  const tokens = raw.split(/\s*[,;]\s*/).filter(Boolean);
  if (!tokens.every((t) => /^[A-Za-z]{2}$/.test(t))) return raw;
  return tokens.map((t) => countryName(t) ?? t).join(', ');
}

// ---------- Plazo: atajos ----------

/** Abierto y cierra en 7 días o menos (incluye hoy). */
export function closingSoon(o: Pick<Opportunity, 'status' | 'application_deadline'>): boolean {
  if (isClosed(o)) return false;
  const days = daysUntil(o.application_deadline);
  return days != null && days >= 0 && days <= CLOSING_SOON_DAYS;
}

// ---------- Coste y requisitos ----------

function numericCost(cost: unknown): number | null {
  if (cost == null || cost === '') return null;
  const n = typeof cost === 'number' ? cost : Number(String(cost).replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

const FREE_RE = /gratu|sin coste|free of charge|no (participation )?fee|0 ?€/i;

/**
 * Resumen corto de lo que cuesta. null = no se sabe: la pantalla muestra
 * "Consulta qué está cubierto".
 */
export function costSummary(o: Pick<Opportunity, 'cost' | 'type' | 'covered_costs'>): string | null {
  const n = numericCost(o.cost);
  if (n === 0) return 'Gratis';
  if (n != null && n > 0) return `Cuota de ${formatNumber(n)} €`;
  if (o.type === 'VOLUNTEERING') return 'Gratis: viaje, alojamiento, comida, seguro y dinero de bolsillo cubiertos';
  if (o.covered_costs && FREE_RE.test(o.covered_costs)) return 'Gratis (alojamiento y comida cubiertos)';
  return null;
}

/**
 * Coste en forma corta para la línea de fechas de la tarjeta: 'Gratis', 'Cuota 300 €' o null
 * (no se sabe: la tarjeta no dice nada). Mismo criterio que `costSummary`.
 *   costShort({ cost: 0 }) → 'Gratis'; costShort({ cost: 300 }) → 'Cuota 300 €';
 *   costShort({ cost: null, type: 'VOLUNTEERING' }) → 'Gratis'; sin datos → null.
 */
export function costShort(o: Pick<Opportunity, 'cost' | 'type' | 'covered_costs'>): 'Gratis' | `Cuota ${string} €` | null {
  const n = numericCost(o.cost);
  if (n === 0) return 'Gratis';
  if (n != null && n > 0) return `Cuota ${formatNumber(n)} €`;
  if (o.type === 'VOLUNTEERING') return 'Gratis';
  if (o.covered_costs && FREE_RE.test(o.covered_costs)) return 'Gratis';
  return null;
}

export type SpainEligibility = 'yes' | 'check' | 'unknown';

/**
 * ¿Pueden apuntarse residentes en España?
 * 'yes' = ES está en la lista; 'check' = hay lista y ES no aparece; 'unknown' = no hay lista.
 */
export function spainEligibility(o: Pick<Opportunity, 'eligibility_country_codes'>): SpainEligibility {
  const codes = o.eligibility_country_codes;
  if (!Array.isArray(codes) || codes.length === 0) return 'unknown';
  return codes.some((c) => typeof c === 'string' && c.trim().toUpperCase() === 'ES') ? 'yes' : 'check';
}

// ---------- Títulos ----------

/** Hermes antiguo no entiende \p{…}: si falla, rangos equivalentes a mano. */
function makeRegex(source: string, fallback: string, flags: string): RegExp {
  try {
    return new RegExp(source, flags);
  } catch {
    return new RegExp(fallback, flags);
  }
}

const PICTO_RE = makeRegex(
  '\\p{Extended_Pictographic}',
  '[\\u00a9\\u00ae\\u203c\\u2049\\u2122\\u2139\\u2194-\\u21ff\\u2300-\\u23ff\\u24c2\\u25a0-\\u27bf\\u2900-\\u297f\\u2b00-\\u2bff\\u3030\\u303d\\u3297\\u3299]|[\\ud83c-\\ud83e][\\udc00-\\udfff]',
  'gu',
);
/** Selectores de variación, ZWJ, tonos de piel, letras-bandera, keycap y ❗❕‼ por si acaso. */
const EMOJI_EXTRAS_RE = /[︎️‍⃣❗❕‼]|\uD83C[\uDFFB-\uDFFF]|\uD83C[\uDDE6-\uDDFF]/g;

/** Siglas que se quedan en mayúsculas al pasar un título GRITADO a frase. */
const KEEP_UPPER = new Set([
  'ESC', 'YE', 'TC', 'EU', 'UE', 'CES', 'EVS', 'SVE', 'NGO', 'ONG', 'UN', 'ONU', 'SDG', 'SDGS', 'ODS',
  'ICT', 'TIC', 'AI', 'IA', 'VR', 'AR', 'DIY', 'LGBT', 'LGBTI', 'LGBTQ', 'LGBTQI', 'NFE', 'ENF', 'STEM',
  'UK', 'USA', 'EU-', 'KA1', 'KA2', 'SALTO', 'TCA', 'E+', 'EPVP', 'GSA',
]);
const ROMAN_RE = /^(X{0,3})(IX|IV|V?I{0,3})$/;

function isLetter(ch: string): boolean {
  return ch.toLowerCase() !== ch.toUpperCase();
}

function countryWords(): Set<string> {
  const out = new Set<string>();
  for (const [es, en] of Object.values(COUNTRIES)) {
    for (const n of [es, en]) if (!n.includes(' ')) out.add(n.toLowerCase());
  }
  return out;
}
let COUNTRY_WORDS: Set<string> | null = null;

function sentenceCase(text: string): string {
  COUNTRY_WORDS ??= countryWords();
  const words = text.split(/(\s+)/);
  const out = words.map((w) => {
    if (!w.trim()) return w;
    const core = w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}+]+$/gu, '');
    const upperCore = core.toUpperCase();
    const hasDigit = /\d/.test(core);
    const mixed = core !== upperCore; // ya tenía minúsculas: se respeta
    if (mixed || hasDigit || KEEP_UPPER.has(upperCore) || (core.length > 1 && ROMAN_RE.test(core))) return w;
    const lower = w.toLowerCase();
    if (COUNTRY_WORDS!.has(core.toLowerCase())) {
      return lower.replace(core.toLowerCase(), core.charAt(0) + core.slice(1).toLowerCase());
    }
    return lower;
  });
  // Mayúscula al principio y tras punto, dos puntos, "·", "!" o "?".
  let joined = out.join('');
  joined = joined.replace(/(^|[.:!?·]\s+|^[^\p{L}]*)(\p{Ll})/gu, (_m, pre: string, ch: string) => pre + ch.toUpperCase());
  return joined;
}

function safeSentenceCase(text: string): string {
  try {
    return sentenceCase(text);
  } catch {
    // Sin soporte de \p{…}: primera letra en mayúscula y el resto tal cual en minúsculas.
    const lower = text.toLowerCase();
    return lower.charAt(0).toUpperCase() + lower.slice(1);
  }
}

/**
 * Título limpio para tarjetas y ficha: sin emojis ni ❗, " | " → " · ", y si viene casi todo en
 * MAYÚSCULAS lo pasa a frase (manteniendo siglas como ESC, YE, EU y números romanos).
 * Nunca devuelve vacío: si no queda nada, el original.
 */
export function cleanTitle(title: string | null | undefined): string {
  const original = (title ?? '').trim();
  if (!original) return '';
  let t = original.replace(PICTO_RE, ' ').replace(EMOJI_EXTRAS_RE, '');
  t = t.replace(/\s*\|\s*/g, ' · ');
  t = t.replace(/\s+/g, ' ').replace(/\s+([,.;)])/g, '$1').replace(/\(\s+/g, '(');
  t = t.replace(/^[\s·\-–—:|,]+|[\s·\-–—:|,]+$/g, '').trim();
  if (!t) return original;

  let letters = 0;
  let upper = 0;
  for (const ch of t) {
    if (!isLetter(ch)) continue;
    letters++;
    if (ch === ch.toUpperCase()) upper++;
  }
  if (letters >= 4 && upper / letters > 0.6) t = safeSentenceCase(t);
  return t || original;
}

// ---------- Textos extraídos ----------

/** Frases de relleno de la extracción ("ver el infopack", "no se especifica"…). */
const FILLER_RE = /as per the info-?pack|check the link above|see (the )?info-?pack|no se especifican?|not specified|^\s*n\/a\s*$/i;
/** Por debajo de esto, un texto extraído no aporta nada. */
const FILLER_MIN_CHARS = 12;

/**
 * ¿Es relleno de la extracción y no merece una sección? true si está vacío, es muy corto
 * (<12 caracteres) o es una frase de relleno.
 *   isFillerText('As per the infopack') → true; isFillerText('N/A') → true;
 *   isFillerText('Alojamiento en albergue compartido') → false.
 */
export function isFillerText(
  text: string | null | undefined,
  { minChars = FILLER_MIN_CHARS }: { minChars?: number } = {},
): boolean {
  const t = (text ?? '').trim();
  if (!t || t.length < minChars) return true;
  return FILLER_RE.test(t);
}

/*
 * ¿Un texto está en inglés? Heurística sencilla por palabras vacías muy frecuentes, suficiente
 * para avisar "Texto original en inglés" y para que VoiceOver/TalkBack lo lean con voz inglesa
 * (`accessibilityLanguage="en"`). Ante la duda, false (se trata como español).
 */
const EN_WORDS = new Set(
  'the and of to in for with on is are be will you your we our this that from at by as an it they their have has can who which youth young people exchange training course volunteering participants project'.split(
    ' ',
  ),
);
const ES_WORDS = new Set(
  'el la los las de del y en para con por un una que es son se su sus al lo como jóvenes intercambio curso voluntariado participantes proyecto'.split(
    ' ',
  ),
);

function languageCounts(text: string): { en: number; es: number; words: number } {
  const words = text.toLowerCase().match(/[a-záéíóúüñ]+/g) ?? [];
  let en = 0;
  let es = 0;
  for (const w of words) {
    if (EN_WORDS.has(w)) en++;
    if (ES_WORDS.has(w)) es++;
  }
  return { en, es, words: words.length };
}

/**
 * Texto largo (descripción): ≥4 palabras inglesas frecuentes y el doble que españolas.
 *   looksEnglish('The project will bring together young people from five countries to work on…') → true
 *   looksEnglish('Un intercambio para jóvenes sobre sostenibilidad') → false
 */
export function looksEnglish(text: string | null | undefined): boolean {
  const t = (text ?? '').trim();
  if (!t) return false;
  if (/[ñ¿¡]|ción\b/i.test(t)) return false;
  const { en, es, words } = languageCounts(t);
  if (words < 12) return looksEnglishShort(t);
  return en >= 4 && en >= es * 2;
}

/** Texto corto (título): al menos dos palabras inglesas y ninguna española, sin tildes ni ñ. */
export function looksEnglishShort(text: string | null | undefined): boolean {
  const t = (text ?? '').trim();
  if (!t || /[ñ¿¡áéíóú]/i.test(t)) return false;
  const { en, es } = languageCounts(t);
  return en >= 2 && es === 0;
}
