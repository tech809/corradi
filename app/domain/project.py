"""Utilidades de dominio: parseo de campos extraídos por el LLM y hash de deduplicación."""
from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.eligibility import parse_eligibility_label


def _add_months(d: date, months: int) -> date:
    """Suma meses a una fecha sin depender de dateutil (recorta el día si el mes es más corto)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)

# Campos que el LLM debe extraer del mensaje (orden = el del prompt).
EXTRACTABLE_FIELDS = [
    "title", "type", "topic", "organiser_name", "country_code", "location",
    "start_date", "end_date", "application_deadline",
    "infopack_url", "application_url",
    "max_participants", "participant_min_age", "participant_max_age",
    "cost", "contact_information",
    "detailed_description", "programme_details", "learning_outcomes",
    "participant_profile", "accommodation_details", "covered_costs",
    "travel_details", "eligibility_countries",
    "image_url", "image_credit", "image_source_url", "image_origin",
]


def parse_date(value) -> date | None:
    """Acepta DD/MM/YYYY (preferido por el prompt) o ISO YYYY-MM-DD."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


_URL_RE = re.compile(r"^https?://", re.I)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_url(value) -> str | None:
    """None si value no es una URL absoluta de verdad (p.ej. el nombre de un fichero
    que el LLM confundio con un enlace) -- mejor no mostrar boton que mostrar uno roto.
    Caso real (2026-07-29): a veces "donde apuntarse" es un email suelto, no un
    formulario -- se convierte a mailto: en vez de descartarlo (sigue siendo una forma
    valida de apuntarse, con href="correo@x.com" a secas el boton no hacia nada)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if _URL_RE.match(value):
        return value
    if _EMAIL_RE.match(value):
        return f"mailto:{value}"
    return None


# Etiquetas que el LLM suele dejar en `contact_information`, muchas veces SIN valor
# ("... E-Mail: Phone: x"). Sirven para (a) borrar las que quedan colgando vacías y
# (b) quitar la etiqueta cuando sí llevan dato, dejando solo el dato.
_CONTACT_LABEL = (
    r"(?:e[-\s]?mail|email|correo(?:\s+electr[oó]nico)?|mail|phone|tel(?:[eé]fono)?|"
    r"whats\s?app|m[oó]vil|mobile|cell|web(?:site)?|sitio\s+web|contact(?:o)?|"
    r"persona\s+de\s+contacto|nombre|name)"
)
_CONTACT_JUNK = {
    "", "-", "--", "—", "–", ".", "..", "...", "/", "n/a", "na", "none", "null", "nil",
    "x", "xx", "xxx", "tbd", "tba", "s/n", "sn", "por confirmar", "a confirmar",
    "sin datos", "no disponible", "ver infopack", "consultar infopack", "en el infopack",
    "see infopack", "in infopack", "check infopack", "infopack",
}
_CONTACT_EMAIL_RE = re.compile(r"[^\s@,;]+@[^\s@,;]+\.[^\s@,;]{2,}")
_CONTACT_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{6,}\d")
# Una URL o un @handle también son vías de contacto válidas (Instagram, t.me, web…).
_CONTACT_LINK_RE = re.compile(
    r"https?://|www\.|(?:instagram|facebook|linkedin|t)\.(?:com|me)/|@[\w.]{2,}", re.I
)


def clean_contact(value) -> str | None:
    """Sanea `contact_information` extraído por el LLM: quita etiquetas colgando sin valor
    ('E-Mail: Phone: x'), placeholders ('-', 'x', 'ver infopack') y separadores sueltos.
    Devuelve None cuando lo que queda no permite contactar de verdad (sin email, teléfono
    ni enlace/handle): mejor no enseñar la línea "Contacto" que enseñar ruido."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = " ".join(value.split())
    junk_alt = "|".join(
        re.escape(j) for j in sorted(_CONTACT_JUNK, key=len, reverse=True) if j
    )
    # 1) etiqueta + valor vacío/junk, hasta la siguiente etiqueta / coma / ; / fin
    text = re.sub(
        rf"\b{_CONTACT_LABEL}\s*[:\-]?\s*(?:{junk_alt})?\s*(?=\b{_CONTACT_LABEL}\b|[,;]|$)",
        " · ", text, flags=re.I,
    )
    # 2) etiqueta pegada a un valor real: se quita la etiqueta, se deja el valor
    text = re.sub(rf"\b{_CONTACT_LABEL}\s*[:\-]\s*", " · ", text, flags=re.I)
    # 3) separadores de lista (NO '/', rompería URLs) y bordes
    text = re.sub(r"\s*[,;|]\s*|\s+[-–—]\s+", " · ", text)
    text = re.sub(r"(?:\s*·\s*)+", " · ", text).strip(" ·,;:-")
    text = " ".join(text.split())
    if not text or text.lower() in _CONTACT_JUNK:
        return None
    if not (_CONTACT_EMAIL_RE.search(text) or _CONTACT_PHONE_RE.search(text)
            or _CONTACT_LINK_RE.search(text)):
        return None
    return text


def parse_int(value) -> int | None:
    try:
        return int(str(value).strip()) if value not in (None, "", "null") else None
    except (ValueError, TypeError):
        return None


def parse_decimal(value) -> Decimal | None:
    if value in (None, "", "null"):
        return None
    try:
        return Decimal(str(value).replace(",", ".").replace("€", "").strip())
    except (InvalidOperation, ValueError):
        return None


# Señales de "esto cierra ya" en el texto original: si además no hay fecha límite explícita,
# la deadline estimada es mucho más corta (LAST_MINUTE_DEADLINE_DAYS en vez de la normal).
# Se buscan sobre el texto plegado (minúsculas, sin tildes, guiones/barras como espacio) y
# SIEMPRE con límites de palabra: "urgente" no debe saltar dentro de "insurgente", ni
# "replacement" en "hip replacement", ni "last" en "last year". Las palabras sueltas y
# ambiguas ("urgente", "replacement", "sustituto") solo cuentan dentro de construcciones
# que en una convocatoria significan "falta gente ya" (ver tests/test_last_minute.py).
_NUM_SMALL = r"(?:1|2|3|una?|one|two|three|dos|tres)"
_LAST_MINUTE_PATTERNS = [re.compile(p) for p in (
    # ES: última hora / último momento / última llamada / última oportunidad
    r"\bultima(?:s)? (?:hora|horas|llamada|oportunidad)\b",
    r"\bultimo momento\b",
    # ES: últimas plazas / vacantes / sitios / lugares (también singular)
    r"\bultim[ao]s? (?:plazas?|vacantes?|sitios?|lugares?|huecos?)\b",
    r"\bplaza (?:libre|disponible|vacante)\b",
    rf"\b(?:solo |solamente |unicamente )?quedan? (?:solo |solamente )?{_NUM_SMALL} (?:plazas?|sitios?|huecos?)\b",
    r"\bquedan pocas plazas\b",
    # ES: urgencia en construcciones de convocatoria
    r"\b(?:llamamiento|convocatoria|busqueda|plaza|plazas) urgentes?\b",
    r"\bse buscan? (?:\w+ ){0,3}urgente(?:mente)?\b",
    r"\bbuscamos (?:\w+ ){0,3}urgente(?:mente)?\b",
    r"\burgente(?:mente)? (?:se )?busca(?:n|mos)?\b",
    # ES: sustitutos (bajas de participantes)
    r"\bbusca(?:n|mos)? (?:\w+ ){0,3}sustitut[oa]s?\b",
    r"\bsustitut[oa] [oa]\b",          # "sustituto/a" tras plegar la barra
    r"\bcomo sustitut[oa]s?\b",
    r"\b(?:plaza|participante)s? (?:de )?sustitu(?:to|ta|cion)\b",
    # ES: empieza en pocos días
    r"\b(?:empieza|comienza|arranca|sale|salida)\w* (?:en|dentro de) "
    r"(?:unos (?:pocos )?|pocos |\d{1,2} |dos |tres |cuatro |cinco )dias\b",
    r"\b(?:empieza|comienza|arranca)\w* (?:la semana que viene|la proxima semana|esta semana|manana|pasado manana)\b",
    # EN
    r"\blast ?minute\b",
    r"\blast (?:call|chance)\b",
    r"\blast (?:places?|spots?|seats?|vacanc(?:y|ies))\b",
    rf"\b(?:only )?{_NUM_SMALL} (?:places?|spots?|seats?) left\b",
    r"\bfew (?:places?|spots?|seats?) left\b",
    r"\burgent (?:call|search|need|replacement|opportunity|vacanc(?:y|ies))\b",
    r"\burgently (?:looking|searching|seeking|needed|wanted|need)\b",
    r"\b(?:looking|searching|seeking) for (?:\w+ ){0,2}replacements?\b",
    r"\b(?:need|needs|needed) (?:\w+ ){0,2}replacements?\b",
    r"\breplacement (?:participants?|volunteers?|needed|wanted|places?|spots?)\b",
    r"\bas (?:a )?replacements?\b",
    r"\basap\b",
    r"\b(?:starts?|starting|begins?|beginning) (?:in|within) "
    r"(?:a few|few|\d{1,2}|one|two|three|four|five) days?\b",
    r"\b(?:starts?|starting|begins?) (?:next week|this week|tomorrow)\b",
)]
# "URGENTE" / "URGENT" en mayúsculas o como titular ("Urgente:", "¡Urgente!") sí es una
# señal de última hora; "urgente" en minúsculas dentro de una frase normal ("ayuda
# humanitaria urgente") no. Esto se mira sobre el texto ORIGINAL (sin plegar mayúsculas).
_URGENT_BANNER_RE = re.compile(
    r"(?<!\w)(?:URGENTE|URGENT)(?!\w)"
    r"|^[^\w\n]*[Uu]rgente?\s*[!:]",
    re.M,
)


def _fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar 'Última' / 'ultima' / 'ÚLTIMA' igual."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def is_last_minute(text: str | None) -> bool:
    """True si el mensaje anuncia última hora / últimas plazas / urgencia por cubrir plaza
    (ES y EN). Firma estable: la usa también la serialización de la web (etiqueta
    "Last call")."""
    if not text:
        return False
    if _URGENT_BANNER_RE.search(text):
        return True
    folded = re.sub(r"[\s\-/_]+", " ", _fold(text))
    return any(p.search(folded) for p in _LAST_MINUTE_PATTERNS)


_ONLINE_HINTS = ["online", "zoom", "virtual", "remoto", "remote", "teams", "webinar", "e-learning", "elearning"]


def is_online_only(location: str | None) -> bool:
    """True si la ubicación indica una actividad 100% online, sin lugar físico — CORRADI-
    BOT es sobre movilidad presencial, así que estas se descartan. Bug real encontrado
    (2026-07-26): "ID Talks: Social Sport" (location="Online (Zoom)") se coló publicada vía
    el scraper de SALTO. Ubicación vacía/desconocida NO cuenta como online (eso es un dato
    que falta, no una señal de que sea online) — se necesita una pista positiva."""
    if not location:
        return False
    folded = _fold(location)
    return any(re.search(rf"\b{hint}\b", folded) for hint in _ONLINE_HINTS)


def make_hash(title: str | None, country_code: str | None, start_date: date | None) -> str:
    content = f"{title or ''}{country_code or ''}{start_date or ''}"
    return hashlib.md5(content.encode()).hexdigest()


def cap_estimated_deadline(deadline: date, start_date: date | None, ref_day: date) -> date:
    """Una deadline ESTIMADA nunca puede caer el día de inicio o después: se recorta al día
    anterior al inicio, pero nunca antes de hoy (`ref_day`). Caso real (2026-11):
    CORRADI-2026-1020 empezaba el 07-11 y la estimada (envío + 5 días) era el 09-11."""
    if start_date is None:
        return deadline
    return max(ref_day, min(deadline, start_date - timedelta(days=1)))


# --- Títulos -----------------------------------------------------------------------------

# Código oficial de proyecto Erasmus+/ESC: 2026-1-TR01-ESC51-VTJ-000400833,
# 2025-1-ES02-KA152-YOU-000123456… A veces es el título entero, a veces un prefijo.
_PROJECT_CODE_RE = re.compile(
    r"\b(?:19|20)\d{2}-\d-[A-Z]{2}\d{2}-[A-Z0-9]{2,8}-[A-Z0-9]{2,8}-\d{5,10}\b", re.I
)
# Siglas que se conservan en mayúsculas al pasar un título GRITADO a tipo título.
_ACRONYMS = {
    "ESC", "EU", "UE", "EVS", "NGO", "NGOS", "ONG", "ONGS", "YE", "TC", "ICT", "TIC", "STEM",
    "STEAM", "LGBT", "LGBTI", "LGBTQ", "LGBTQI", "LGBTIQ", "SDG", "SDGS", "ODS", "DIY", "AI",
    "IA", "ONU", "UNESCO", "UNICEF", "UK", "USA", "CV", "VR", "ESN", "SALTO", "DJ", "PR",
    "TV", "CEO", "SMM", "HIV", "VIH", "SOS", "ASAP", "FAQ", "AFS", "YMCA", "EYP", "GDPR",
    "WWF", "ICYE", "EFIL", "CSR", "NFE", "HR", "EAC", "KA", "OMIX", "APS", "ETS",
}
_ROMAN = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "XIII", "XIV", "XV", "XX"}
# Palabras que van en minúscula dentro de un título (no al principio ni tras '(' '-' '|' ':').
_SMALL_WORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the",
    "to", "with", "vs", "via",
    "de", "del", "la", "las", "el", "los", "en", "y", "e", "o", "u", "con", "para", "por",
    "al", "sin", "di", "da", "per", "il", "le", "les", "au", "aux", "un", "une", "et", "du",
    "des", "allo", "alla", "nel", "nella", "und", "der", "die", "das",
}
_VOWELS = set("aeiouy")


def _is_shouting(text: str) -> bool:
    """True si el texto va entero en mayúsculas (al menos 4 letras y ninguna minúscula).
    Los títulos con mayúsculas mezcladas a propósito ('You FuTuRe') no se tocan."""
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and not any(c.islower() for c in letters)


def _lower(word: str) -> str:
    # 'İ'.lower() en Python da 'i̇' (i + punto combinante): en títulos turcos queda feo.
    return word.replace("İ", "i").lower()


def smart_title_case(text: str) -> str:
    """'ESC IN ERZURUM/TURKIYE' → 'ESC in Erzurum/Turkiye'; conserva siglas conocidas,
    números romanos, palabras sin vocales ('VTJ') y siglas pegadas a cifras ('COMIC4EU' →
    'Comic4EU'). Pensado SOLO para títulos gritados (ver `_is_shouting`)."""
    out: list[str] = []
    pos = 0
    first = True
    for m in re.finditer(r"[^\W\d_]+", text):
        out.append(text[pos:m.start()])
        word, start = m.group(0), m.start()
        prev = text[start - 1] if start else ""
        prev2 = text[start - 2] if start > 1 else ""
        nxt = text[m.end()] if m.end() < len(text) else ""
        folded = _fold(word)
        if (prev and prev in "'’") or (prev == "(" and prev2.isalpha()):
            new = _lower(word)  # WOMEN’S → Women’s, YOU(TH) → You(th)
        elif word.upper() in _ACRONYMS or word.upper() in _ROMAN:
            new = word.upper()
        elif not (set(folded) & _VOWELS) and len(word) >= 2:
            new = word  # 'VTJ', 'TR', 'BWA': sigla
        elif (prev.isdigit() or nxt.isdigit()) and len(word) <= 3:
            new = word  # '4EU', 'KA152'
        elif (not first and folded in _SMALL_WORDS and prev == " "
              and text[:start].rstrip()[-1:] not in tuple("(-–—|:/")
              and re.match(r"\s+[^\W\d_]", text[m.end():])):
            new = _lower(word)
        else:
            new = word[0].upper() + _lower(word[1:])
        out.append(new)
        pos = m.end()
        first = False
    out.append(text[pos:])
    return "".join(out)


def _fallback_title(organiser: str | None, town: str | None, prefix: str) -> str | None:
    org = " ".join(organiser.split()) if isinstance(organiser, str) and organiser.strip() else None
    place = " ".join(town.split()) if isinstance(town, str) and town.strip() else None
    if org and _is_shouting(org):
        org = smart_title_case(org)
    if place and _is_shouting(place):
        place = smart_title_case(place)
    if org and place:
        return f"{prefix} con {org} en {place}"
    if org:
        return f"{prefix} con {org}"
    if place:
        return f"{prefix} en {place}"
    return None


def clean_title(
    title: str | None, *, organiser: str | None = None, town: str | None = None,
    fallback_prefix: str = "Proyecto Erasmus+", default: str | None = None,
) -> str | None:
    """Normaliza títulos de baja calidad:
      - quita códigos oficiales de proyecto ('2026-1-TR01-ESC51-VTJ-000400833 TÍTULO' →
        'TÍTULO'); si el título ERA solo el código, lo sustituye por uno derivado del
        organizador/ciudad ('Voluntariado ESC con X en Y') o por `default`;
      - pasa los títulos gritados (todo mayúsculas) a tipo título conservando siglas.
    Si no hay nada mejor con lo que sustituir un código, se deja el título como estaba."""
    if not isinstance(title, str) or not title.strip():
        return default if default is not None else title
    original = " ".join(title.split())
    t = _PROJECT_CODE_RE.sub(" ", original)
    t = re.sub(r"\(\s*\)|\[\s*\]", " ", t)
    t = " ".join(t.split()).strip(" -–—|:·,;/")
    if sum(c.isalpha() for c in t) < 3:
        return _fallback_title(organiser, town, fallback_prefix) or default or original
    return smart_title_case(t) if _is_shouting(t) else t


# --- Temáticas ---------------------------------------------------------------------------

def clean_topic(topic: str | None) -> str | None:
    """Quita de la lista de temáticas (separada por comas) los códigos numéricos sueltos
    ('235', '253'…: ids internos de EYP sin etiqueta pública) y los duplicados."""
    if not isinstance(topic, str):
        return topic
    seen: list[str] = []
    for part in topic.split(","):
        part = part.strip()
        if part and not part.isdigit() and part not in seen:
            seen.append(part)
    return ", ".join(seen) or None


# --- Resúmenes ---------------------------------------------------------------------------

# Frases de relleno que no aportan nada en una tarjeta ("See full description and how to
# apply on our website, here."). Solo se quitan del RESUMEN, no de la descripción completa.
_SUMMARY_BOILERPLATE_RE = re.compile(
    r"(?i)(?:^|(?<=[.!?\n]))[ \t]*"
    r"(?:(?:please )?(?:see|read|check|find)(?: out)?\b[^.!?\n]{0,40}"
    r"\b(?:full|complete|whole|more)\b[^.!?\n]{0,40}"
    r"\b(?:description|details|info(?:rmation)?|infopack|info ?pack|offer)\b[^.!?\n]{0,80}"
    r"|(?:read|find out|learn) more\b[^.!?\n]{0,20}(?:here|below|https?://\S+)[^.!?\n]{0,20})"
    r"(?:[.!?]+|$)",
    re.M,
)


def strip_summary_boilerplate(text: str | None) -> str | None:
    if not text:
        return text
    cleaned = _SUMMARY_BOILERPLATE_RE.sub(" ", text)
    lines = [" ".join(line.split()) for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line) or None


def cap_summary(text: str | None, limit: int = 500) -> str | None:
    """Recorta un resumen a `limit` caracteres sin partir frases ni palabras:
      1) si cabe, tal cual;
      2) si hay un final de frase ('. ', '! ', '? ' o fin de línea) en la segunda mitad
         larga del límite (>= 40 %), corta ahí; si la frase no acaba en puntuación
         (p.ej. una línea de lista), añade '…';
      3) si no, corta en la última palabra completa y añade '…'.
    Primero quita el relleno tipo 'See full description… here.'."""
    text = strip_summary_boilerplate(text)
    if not text:
        return None
    text = text.strip()
    if len(text) <= limit:
        return text
    window = text[:limit]
    floor = int(limit * 0.4)
    cut = -1
    for m in re.finditer(r"[.!?…](?=\s)|\n", window):
        if m.start() >= floor:
            cut = m.end() if window[m.start()] != "\n" else m.start()
    if cut == -1:
        cut = window.rfind(" ")
        cut = cut if cut > 0 else limit
    out = text[:cut].rstrip()
    # Un encabezado colgando ("Tareas:") sin lo que anuncia no aporta: se quita esa línea.
    if out.endswith(":") and "\n" in out:
        out = out.rsplit("\n", 1)[0].rstrip()
    if out[-1:] in ".!?…":
        return out
    return out.rstrip(".,;:-–—•·( ") + "…"


def _year_written(year: int, raw_text: str) -> bool:
    """¿El mensaje original escribe ese año? (``2026`` o ``/26``, ``-26``, ``.26`` tras día/mes)."""
    return bool(raw_text) and bool(re.search(rf"\b{year}\b|[/.\-]{year % 100:02d}\b", raw_text))


def _future(d: date | None, ref_day: date, raw_text: str = "") -> date | None:
    """Red de seguridad: si el LLM omite el año y devuelve una fecha ya pasada, la empuja
    al año siguiente. Son siempre convocatorias abiertas a futuro, nunca eventos pasados.

    Si el año SÍ aparece escrito en el mensaje, no se toca: una fecha pasada con año
    explícito es un evento pasado, no un año mal inferido, y moverla lo convertiría en otro."""
    if d is None or d >= ref_day:
        return d
    if _year_written(d.year, raw_text):
        return d
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 feb en año no bisiesto
        return d.replace(year=d.year + 1, day=28)


_TITLE_FALLBACK_PREFIX = {
    "YOUTH_EXCHANGE": "Intercambio juvenil", "TRAINING_COURSE": "Curso de formación",
    "VOLUNTEERING": "Voluntariado",
}


def normalize(
    fields: dict,
    ref_day: date,
    default_deadline_days: int,
    raw_text: str = "",
    last_minute_deadline_days: int = 2,
    max_deadline_months: int = 3,
) -> dict:
    """Convierte el dict crudo del LLM en tipos correctos y aplica el fallback de deadline.

    Añade banderas que no van a la BD pero usa el pipeline:
      - `deadline_in_past`: la fecha límite que trae el mensaje ya pasó (se rechaza el envío).
      - `deadline_too_far`: la fecha límite final cae más allá de `max_deadline_months` desde
        hoy (red de seguridad frente a años mal inferidos, p.ej. un LLM que empuja una fecha
        un año de más; se rechaza el envío en vez de publicar una deadline absurda).
      - `last_minute`: el mensaje habla de última hora / últimas plazas.
      - `is_online`: la ubicación indica una actividad 100% online, sin lugar físico (se
        rechaza el envío — ver `is_online_only`).
    """
    out = dict(fields)
    source_text = raw_text or fields.get("raw_message") or ""
    out["start_date"] = _future(parse_date(fields.get("start_date")), ref_day, source_text)
    out["end_date"] = _future(parse_date(fields.get("end_date")), ref_day, source_text)

    stated_deadline = parse_date(fields.get("application_deadline"))
    # Se comprueba ANTES de _future: si el mensaje trae una fecha límite ya pasada no hay que
    # empujarla al año siguiente, hay que rechazar la oportunidad por estar fuera de plazo.
    out["deadline_in_past"] = stated_deadline is not None and stated_deadline < ref_day
    out["stated_deadline"] = stated_deadline

    last_minute = is_last_minute(raw_text or fields.get("raw_message") or "")
    out["last_minute"] = last_minute

    deadline = _future(stated_deadline, ref_day, source_text)
    if deadline is None:
        days = last_minute_deadline_days if last_minute else default_deadline_days
        deadline = cap_estimated_deadline(
            ref_day + timedelta(days=days), out["start_date"], ref_day
        )
        out["deadline_estimated"] = True
    else:
        out["deadline_estimated"] = False
    out["application_deadline"] = deadline
    out["deadline_too_far"] = deadline > _add_months(ref_day, max_deadline_months)
    out["is_online"] = is_online_only(fields.get("location"))

    out["max_participants"] = parse_int(fields.get("max_participants"))
    out["participant_min_age"] = parse_int(fields.get("participant_min_age"))
    out["participant_max_age"] = parse_int(fields.get("participant_max_age"))
    out["cost"] = parse_decimal(fields.get("cost"))

    # country en mayúsculas alpha-2 si parece un código
    cc = (fields.get("country_code") or fields.get("country") or "")
    out["country_code"] = cc.strip().upper()[:2] or None

    organiser = fields.get("organiser_name")
    out["organiser_name"] = organiser.strip() if isinstance(organiser, str) and organiser.strip() else None
    out["title"] = clean_title(
        fields.get("title"), organiser=out["organiser_name"],
        fallback_prefix=_TITLE_FALLBACK_PREFIX.get(fields.get("type"), "Proyecto Erasmus+"),
    )
    out["topic"] = clean_topic(fields.get("topic"))

    # Red de seguridad barata (sin LLM) contra enlaces que no son enlaces de verdad --
    # bug real encontrado (2026-07-29): el scraper de SALTO a veces solo conseguia el
    # TEXTO visible de un enlace de descarga (p.ej. "Art-Mind, INFO PACK.pdf", el nombre
    # del fichero) en vez de su href, y el LLM lo devolvia tal cual como infopack_url --
    # se guardaba un nombre de fichero, no una URL, y el boton "Infopack" quedaba roto
    # (enlazaba, sin querer, a una ruta relativa del propio mapa). Aplica a cualquier
    # fuente (Telegram, WhatsApp, SALTO), no solo a la que lo disparo la primera vez.
    out["infopack_url"] = _clean_url(fields.get("infopack_url"))
    out["application_url"] = _clean_url(fields.get("application_url"))
    out["contact_information"] = clean_contact(fields.get("contact_information"))
    codes, scope = parse_eligibility_label(fields.get("eligibility_countries"))
    out["eligibility_country_codes"] = codes
    out["eligibility_scope"] = scope
    return out


def _organiser_key(name: str) -> str:
    """Clave de comparación para asociaciones: sin acentos, minúsculas, espacios colapsados
    ('Tierra Nómada' y 'tierra  nomada' dan la misma clave)."""
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def canonicalize_organiser(name: str | None, existing: list[str]) -> str | None:
    """Si `name` es (esencialmente) una asociación ya existente en la BD, devuelve el nombre
    tal cual está guardado allí en vez del que acaba de extraer la IA -- para que 'Tierra
    Nómada' y 'tierra nomada' no cuenten como dos asociaciones distintas en /estadisticas.
    Coincidencia exacta (normalizada) primero; si no, una muy similar (typo/orden de
    palabras) via difflib. Por debajo del umbral, se deja el nombre nuevo tal cual."""
    if not name or not existing:
        return name
    key = _organiser_key(name)
    by_key = {_organiser_key(e): e for e in existing if e}
    if key in by_key:
        return by_key[key]
    match = difflib.get_close_matches(key, list(by_key.keys()), n=1, cutoff=0.88)
    if match:
        return by_key[match[0]]
    return name
