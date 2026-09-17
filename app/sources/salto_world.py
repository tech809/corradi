"""Reglas SALTO exclusivas del catálogo internacional."""
from __future__ import annotations

import re

from app.sources.salto_youth import _TYPE_COUNTRY_RE, _strip_tags

# Países que SALTO agrupa habitualmente bajo "Erasmus+ Youth Programme countries".
PROGRAMME_COUNTRY_CODES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES",
    "SE", "IS", "LI", "NO", "MK", "RS", "TR", "CH",
})
NEIGHBOURING_COUNTRY_CODES = frozenset({
    "AL", "DZ", "AM", "AZ", "BY", "BA", "EG", "GE", "IL", "JO", "XK", "LB", "LY",
    "MD", "ME", "MA", "PS", "RU", "SY", "TN", "UA",
})

_COUNTRIES = {
    "albania": "AL", "algeria": "DZ", "armenia": "AM", "austria": "AT",
    "azerbaijan": "AZ", "belarus": "BY", "belgium": "BE", "belgium - de": "BE",
    "belgium - fl": "BE", "belgium - fr": "BE", "bosnia and herzegovina": "BA",
    "bulgaria": "BG", "croatia": "HR", "cyprus": "CY", "czech republic": "CZ",
    "czechia": "CZ", "denmark": "DK", "egypt": "EG", "estonia": "EE", "finland": "FI",
    "france": "FR", "georgia": "GE", "germany": "DE", "greece": "GR", "hungary": "HU",
    "iceland": "IS", "ireland": "IE", "israel": "IL", "italy": "IT", "jordan": "JO",
    "kosovo": "XK", "kosovo * un resolution": "XK", "latvia": "LV", "lebanon": "LB",
    "libya": "LY", "liechtenstein": "LI", "lithuania": "LT", "luxembourg": "LU",
    "malta": "MT", "moldova": "MD", "montenegro": "ME", "morocco": "MA",
    "netherlands": "NL", "north macedonia": "MK", "norway": "NO", "palestine": "PS",
    "poland": "PL", "portugal": "PT", "republic of north macedonia": "MK",
    "romania": "RO", "russian federation": "RU", "serbia": "RS", "slovak republic": "SK",
    "slovakia": "SK", "slovenia": "SI", "spain": "ES", "sweden": "SE",
    "switzerland": "CH", "syria": "SY", "tunisia": "TN", "türkiye": "TR",
    "turkiye": "TR", "turkey": "TR", "ukraine": "UA",
}


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


def parse_eligibility_label(label: str | None) -> tuple[list[str], str]:
    """Normaliza también el campo extraído por el bot de aportaciones World."""
    if not label:
        return [], "unknown"
    lowered = label.lower()
    codes: set[str] = set()
    scope = "explicit"
    if "erasmus+ youth programme countries" in lowered or "programme countries" in lowered:
        codes.update(PROGRAMME_COUNTRY_CODES)
        scope = "all_programme"
    if "partner countries neighbouring the eu" in lowered:
        codes.update(NEIGHBOURING_COUNTRY_CODES)
        scope = "neighbouring" if not codes.intersection(PROGRAMME_COUNTRY_CODES) else "all_programme"
    # Match por frases completas para no confundir, por ejemplo, Ireland con Northern Ireland.
    for name, code in _COUNTRIES.items():
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", lowered):
            codes.add(code)
    return sorted(codes), scope if codes else "unknown"
