"""Utilidades de dominio: parseo de campos extraídos por el LLM y hash de deduplicación."""
from __future__ import annotations

import hashlib
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

    out["max_participants"] = parse_int(fields.get("max_participants"))
    out["participant_min_age"] = parse_int(fields.get("participant_min_age"))
    out["participant_max_age"] = parse_int(fields.get("participant_max_age"))
    out["cost"] = parse_decimal(fields.get("cost"))

    # country en mayúsculas alpha-2 si parece un código
    cc = (fields.get("country_code") or fields.get("country") or "")
    out["country_code"] = cc.strip().upper()[:2] or None

    organiser = fields.get("organiser_name")
    out["organiser_name"] = organiser.strip() if isinstance(organiser, str) and organiser.strip() else None
    return out
