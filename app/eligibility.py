"""Normalización compartida de países elegibles para los catálogos ES y World."""
from __future__ import annotations

import re
import unicodedata


PROGRAMME_COUNTRY_CODES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES",
    "SE", "IS", "LI", "NO", "MK", "RS", "TR", "CH",
})
NEIGHBOURING_COUNTRY_CODES = frozenset({
    "AL", "DZ", "AM", "AZ", "BY", "BA", "EG", "GE", "IL", "JO", "XK", "LB", "LY",
    "MD", "ME", "MA", "PS", "RU", "SY", "TN", "UA",
})

# Nombres que aparecen con frecuencia tanto en infopacks ingleses como en mensajes españoles.
_COUNTRIES = {
    "albania": "AL", "alemania": "DE", "algeria": "DZ", "argelia": "DZ",
    "armenia": "AM", "austria": "AT", "azerbaijan": "AZ", "azerbaiyan": "AZ",
    "belarus": "BY", "belgica": "BE", "belgium": "BE", "bosnia and herzegovina": "BA",
    "bosnia y herzegovina": "BA", "bulgaria": "BG", "croacia": "HR", "croatia": "HR",
    "chipre": "CY", "cyprus": "CY", "czech republic": "CZ", "czechia": "CZ",
    "chequia": "CZ", "dinamarca": "DK", "denmark": "DK", "egypt": "EG", "egipto": "EG",
    "estonia": "EE", "finland": "FI", "finlandia": "FI", "france": "FR", "francia": "FR",
    "georgia": "GE", "germany": "DE", "greece": "GR", "grecia": "GR", "hungria": "HU",
    "hungary": "HU", "iceland": "IS", "islandia": "IS", "ireland": "IE", "irlanda": "IE",
    "israel": "IL", "italia": "IT", "italy": "IT", "jordan": "JO", "jordania": "JO",
    "kosovo": "XK", "letonia": "LV", "latvia": "LV", "lebanon": "LB", "libano": "LB",
    "libya": "LY", "libia": "LY", "liechtenstein": "LI", "lithuania": "LT",
    "lituania": "LT", "luxembourg": "LU", "luxemburgo": "LU", "malta": "MT",
    "moldova": "MD", "moldavia": "MD", "montenegro": "ME", "morocco": "MA",
    "marruecos": "MA", "netherlands": "NL", "paises bajos": "NL",
    "north macedonia": "MK", "republic of north macedonia": "MK", "macedonia del norte": "MK", "norway": "NO", "noruega": "NO",
    "palestine": "PS", "palestina": "PS", "poland": "PL", "polonia": "PL",
    "portugal": "PT", "romania": "RO", "rumania": "RO", "russia": "RU", "russian federation": "RU", "rusia": "RU",
    "serbia": "RS", "slovak republic": "SK", "slovakia": "SK", "eslovaquia": "SK",
    "slovenia": "SI", "eslovenia": "SI", "spain": "ES", "espana": "ES",
    "sweden": "SE", "suecia": "SE", "switzerland": "CH", "suiza": "CH",
    "syria": "SY", "siria": "SY", "tunisia": "TN", "tunez": "TN", "turkiye": "TR",
    "turkey": "TR", "turquia": "TR", "ukraine": "UA", "ucrania": "UA",
}


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def parse_eligibility_label(label: str | None) -> tuple[list[str], str]:
    """Convierte una descripción libre en códigos ISO y un alcance comprobable.

    Un resultado ``unknown`` no significa que la persona no sea elegible: indica que la
    convocatoria no aporta una lista suficientemente estructurada para afirmarlo.
    """
    if not label:
        return [], "unknown"
    lowered = _fold(label)
    codes: set[str] = set()
    scope = "explicit"
    programme_phrases = (
        "erasmus+ youth programme countries", "programme countries", "program countries",
        "paises del programa erasmus+", "paises del programa", "paises participantes del programa",
    )
    neighbouring_phrases = (
        "partner countries neighbouring the eu", "neighbouring partner countries",
        "paises socios vecinos de la ue", "paises vecinos de la union europea",
    )
    if any(phrase in lowered for phrase in programme_phrases):
        codes.update(PROGRAMME_COUNTRY_CODES)
        scope = "all_programme"
    if any(phrase in lowered for phrase in neighbouring_phrases):
        codes.update(NEIGHBOURING_COUNTRY_CODES)
        if scope != "all_programme":
            scope = "neighbouring"
    for name, code in _COUNTRIES.items():
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", lowered):
            codes.add(code)
    return sorted(codes), scope if codes else "unknown"
