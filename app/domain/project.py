"""Utilidades de dominio: parseo de campos extraídos por el LLM y hash de deduplicación."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

# Campos que el LLM debe extraer del mensaje (orden = el del prompt).
EXTRACTABLE_FIELDS = [
    "title", "type", "topic", "country_code", "location",
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


def normalize(fields: dict, ref_day: date, default_deadline_days: int) -> dict:
    """Convierte el dict crudo del LLM en tipos correctos y aplica el fallback de deadline."""
    out = dict(fields)
    out["start_date"] = _future(parse_date(fields.get("start_date")), ref_day)
    out["end_date"] = _future(parse_date(fields.get("end_date")), ref_day)

    deadline = _future(parse_date(fields.get("application_deadline")), ref_day)
    if deadline is None:
        deadline = ref_day + timedelta(days=default_deadline_days)
        out["deadline_estimated"] = True
    else:
        out["deadline_estimated"] = False
    out["application_deadline"] = deadline

    out["max_participants"] = parse_int(fields.get("max_participants"))
    out["participant_min_age"] = parse_int(fields.get("participant_min_age"))
    out["participant_max_age"] = parse_int(fields.get("participant_max_age"))
    out["cost"] = parse_decimal(fields.get("cost"))

    # country en mayúsculas alpha-2 si parece un código
    cc = (fields.get("country_code") or fields.get("country") or "")
    out["country_code"] = cc.strip().upper()[:2] or None
    return out
