"""Reglas SALTO exclusivas del catálogo internacional."""
from __future__ import annotations

import re

from app.eligibility import (
    NEIGHBOURING_COUNTRY_CODES,
    PROGRAMME_COUNTRY_CODES,
    parse_eligibility_label,
)

from app.sources.salto_youth import _TYPE_COUNTRY_RE, _strip_tags

def quick_relevance_check(raw_html: str) -> bool | None:
    """Solo Training Courses; nunca filtra por un país residente concreto."""
    flat = re.sub(r"\s+", " ", _strip_tags(raw_html))
    match = _TYPE_COUNTRY_RE.search(flat)
    if not match:
        return None
    return "training course" in match.group(1).lower()


def is_clearly_closed(raw_html: str) -> bool:
    text = _strip_tags(raw_html).lower()
    return "applications are closed" in text or "this activity has already happened" in text


def parse_eligibility(raw_html: str) -> tuple[list[str], str, str | None]:
    """Devuelve códigos ISO, alcance y el texto de elegibilidad mostrado al usuario."""
    flat = re.sub(r"\s+", " ", _strip_tags(raw_html))
    match = _TYPE_COUNTRY_RE.search(flat)
    if not match:
        return [], "unknown", None
    label = match.group(2).strip(" .")
    codes, scope = parse_eligibility_label(label)
    return codes, scope, label
