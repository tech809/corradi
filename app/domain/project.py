"""Utilidades de dominio: parseo de campos extraídos por el LLM y hash de deduplicación."""
from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation


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
_LAST_MINUTE_HINTS = [
    "ultima hora", "ultimas horas", "ultimo momento", "ultima llamada",
    "ultima plaza", "ultimas plazas", "ultimas vacantes", "ultimos sitios",
    "plazas de ultima hora", "last minute", "lastminute", "last place", "last places",
    "last spot", "last spots", "last call", "last seats",
]


def _fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar 'Última' / 'ultima' / 'ÚLTIMA' igual."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def is_last_minute(text: str | None) -> bool:
    """True si el mensaje anuncia última hora / últimas plazas."""
    if not text:
        return False
    folded = _fold(text)
    return any(hint in folded for hint in _LAST_MINUTE_HINTS)


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


def _future(d: date | None, ref_day: date) -> date | None:
    """Red de seguridad: si el LLM omite el año y devuelve una fecha ya pasada, la empuja
    al año siguiente. Son siempre convocatorias abiertas a futuro, nunca eventos pasados."""
    if d is None or d >= ref_day:
        return d
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 feb en año no bisiesto
        return d.replace(year=d.year + 1, day=28)


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
    out["start_date"] = _future(parse_date(fields.get("start_date")), ref_day)
    out["end_date"] = _future(parse_date(fields.get("end_date")), ref_day)

    stated_deadline = parse_date(fields.get("application_deadline"))
    # Se comprueba ANTES de _future: si el mensaje trae una fecha límite ya pasada no hay que
    # empujarla al año siguiente, hay que rechazar la oportunidad por estar fuera de plazo.
    out["deadline_in_past"] = stated_deadline is not None and stated_deadline < ref_day
    out["stated_deadline"] = stated_deadline

    last_minute = is_last_minute(raw_text or fields.get("raw_message") or "")
    out["last_minute"] = last_minute

    deadline = _future(stated_deadline, ref_day)
    if deadline is None:
        days = last_minute_deadline_days if last_minute else default_deadline_days
        deadline = ref_day + timedelta(days=days)
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

    # Red de seguridad barata (sin LLM) contra enlaces que no son enlaces de verdad --
    # bug real encontrado (2026-07-29): el scraper de SALTO a veces solo conseguia el
    # TEXTO visible de un enlace de descarga (p.ej. "Art-Mind, INFO PACK.pdf", el nombre
    # del fichero) en vez de su href, y el LLM lo devolvia tal cual como infopack_url --
    # se guardaba un nombre de fichero, no una URL, y el boton "Infopack" quedaba roto
    # (enlazaba, sin querer, a una ruta relativa del propio mapa). Aplica a cualquier
    # fuente (Telegram, WhatsApp, SALTO), no solo a la que lo disparo la primera vez.
    out["infopack_url"] = _clean_url(fields.get("infopack_url"))
    out["application_url"] = _clean_url(fields.get("application_url"))
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
