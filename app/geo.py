"""Geocodificación de oportunidades para el mapa público.

Estrategia en dos escalones, para que SIEMPRE haya un pin que enseñar:
  1. Ciudad exacta: se pregunta a Nominatim (OpenStreetMap) por el campo `location`.
     Gratis, sin clave de API. Su política de uso pide un User-Agent identificable y
     como mucho 1 petición por segundo — aquí se geocodifica una sola vez por
     oportunidad (máximo unas pocas al día), así que vamos muy por debajo.
  2. Centro del país: si no hay `location`, si Nominatim no encuentra nada o si falla
     la red, se cae al centroide del país. El mapa marca esos pines como aproximados.

El resultado se guarda en las columnas `latitude`/`longitude` de `projects` (existen
desde la migración inicial), así que cada oportunidad se geocodifica UNA vez y nunca más.
"""
from __future__ import annotations

import logging
import re
import unicodedata

log = logging.getLogger("corradi.geo")

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim exige identificarse; si no, bloquea. Ver https://operations.osmfoundation.org/policies/nominatim/
_USER_AGENT = "CORRADI-BOT/1.0 (difusion Erasmus+; general@proactivefuture.eu)"
_TIMEOUT = 10.0

# Centro geográfico aproximado de cada país (fallback cuando no hay ciudad).
# Cubre los destinos habituales de Erasmus+ / Cuerpo Europeo de Solidaridad.
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "ES": (40.24, -3.65), "PT": (39.56, -8.09), "FR": (46.60, 2.53), "IT": (42.80, 12.61),
    "DE": (51.11, 10.42), "AT": (47.62, 14.13), "BE": (50.63, 4.65), "NL": (52.19, 5.53),
    "LU": (49.77, 6.10), "IE": (53.19, -8.03), "PL": (52.10, 19.40), "CZ": (49.80, 15.48),
    "SK": (48.68, 19.50), "HU": (47.17, 19.40), "RO": (45.92, 25.01), "BG": (42.75, 25.48),
    "GR": (39.07, 22.01), "HR": (45.13, 16.40), "SI": (46.13, 14.81), "EE": (58.66, 25.02),
    "LV": (56.88, 24.90), "LT": (55.19, 23.89), "FI": (64.52, 26.03), "SE": (62.02, 15.05),
    "DK": (56.01, 9.50), "NO": (64.51, 12.03), "IS": (64.91, -19.00), "MT": (35.92, 14.41),
    "CY": (35.04, 33.22), "TR": (39.03, 35.22), "RS": (44.03, 20.90), "MK": (41.60, 21.70),
    "ME": (42.79, 19.31), "BA": (44.03, 17.81), "AL": (41.11, 20.10), "XK": (42.60, 20.90),
    "GE": (42.31, 43.42), "AM": (40.30, 45.00), "UA": (48.40, 31.20), "MD": (47.20, 28.50),
    "CH": (46.80, 8.22), "GB": (54.00, -2.00), "LI": (47.16, 9.55), "AZ": (40.30, 47.70),
}

_COUNTRY_LOCATION_NAMES = {
    "ES": {"espana", "spain"}, "PT": {"portugal"}, "FR": {"france", "francia"},
    "IT": {"italy", "italia"}, "DE": {"germany", "alemania", "deutschland"},
    "AT": {"austria"}, "BE": {"belgium", "belgica", "belgique"},
    "NL": {"netherlands", "paises bajos", "holanda"}, "IE": {"ireland", "irlanda"},
    "PL": {"poland", "polonia"}, "CZ": {"czech republic", "chequia", "czechia"},
    "SK": {"slovak republic", "slovakia", "eslovaquia"}, "HU": {"hungary", "hungria"},
    "RO": {"romania", "rumania"}, "BG": {"bulgaria"}, "GR": {"greece", "grecia"},
    "HR": {"croatia", "croacia"}, "SI": {"slovenia", "eslovenia"},
    "EE": {"estonia"}, "LV": {"latvia", "letonia"}, "LT": {"lithuania", "lituania"},
    "FI": {"finland", "finlandia"}, "SE": {"sweden", "suecia"},
    "DK": {"denmark", "dinamarca"}, "NO": {"norway", "noruega"},
    "MT": {"malta"}, "CY": {"cyprus", "chipre"}, "TR": {"turkiye", "turkey", "turquia"},
    "AL": {"albania"}, "LU": {"luxembourg", "luxemburgo"},
}


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]+", " ", value).strip()


def is_country_only_location(location: str | None, country_code: str | None) -> bool:
    """True cuando `location` solo repite el país, sin una localidad concreta."""
    if not location or not country_code:
        return False
    return _fold(location) in _COUNTRY_LOCATION_NAMES.get(country_code.strip().upper()[:2], set())


def country_centroid(country_code: str | None) -> tuple[float, float] | None:
    """Centro aproximado del país, o None si no lo conocemos."""
    if not country_code:
        return None
    return COUNTRY_CENTROIDS.get(country_code.strip().upper()[:2])


def is_country_level(lat, lon, country_code: str | None) -> bool:
    """True si esas coordenadas son exactamente el centroide del país, es decir, un pin
    aproximado y no una ciudad concreta. Evita tener que añadir una columna nueva."""
    centroid = country_centroid(country_code)
    if centroid is None or lat is None or lon is None:
        return False
    return abs(float(lat) - centroid[0]) < 1e-6 and abs(float(lon) - centroid[1]) < 1e-6


def _nominatim_request(params: dict, what: str) -> tuple[float, float] | None:
    """Llama a Nominatim y saca (lat, lon) del primer resultado. Nunca lanza."""
    import httpx

    try:
        resp = httpx.get(
            _NOMINATIM_URL, params={**params, "format": "json", "limit": 1},
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "es,en"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception as e:  # noqa: BLE001 - la geocodificación nunca debe tumbar el pipeline
        log.warning("Nominatim falló para %s: %s", what, e)
        return None
    if not results:
        return None
    try:
        return float(results[0]["lat"]), float(results[0]["lon"])
    except (KeyError, ValueError, TypeError):
        return None


def _nominatim(query: str, country_code: str | None) -> tuple[float, float] | None:
    """Busca un texto libre (ciudad, dirección…), acotado al país si se conoce."""
    params = {"q": query}
    if country_code:
        params["countrycodes"] = country_code.strip().lower()[:2]
    return _nominatim_request(params, repr(query))


def _nominatim_city(city: str, country_code: str | None) -> tuple[float, float] | None:
    """Busca una ciudad de forma estructurada para evitar coincidencias con calles.

    Por ejemplo, la búsqueda libre ``Lugo, España, ES`` devuelve como primer resultado
    una *Calle Lugo* de Galapagar. El campo estructurado ``city=Lugo`` devuelve el
    municipio correcto.
    """
    params = {"city": city}
    if country_code:
        params["countrycodes"] = country_code.strip().lower()[:2]
    return _nominatim_request(params, f"ciudad {city!r}")


def _nominatim_country(country_code: str) -> tuple[float, float] | None:
    """Busca el país entero (consulta estructurada de Nominatim).

    Es el último recurso para destinos que no están en COUNTRY_CENTROIDS: sabiendo el
    país no tiene sentido quedarse sin pin solo porque no esté en una tabla local.
    """
    return _nominatim_request({"country": country_code}, f"país {country_code}")


def geocode(location: str | None, country_code: str | None) -> tuple[float, float] | None:
    """Coordenadas de una oportunidad: ciudad exacta si se puede, centro del país si no.

    Nunca lanza excepción: si todo falla devuelve None y la oportunidad simplemente no
    sale en el mapa (sigue publicándose con normalidad en el canal).
    """
    location = (location or "").strip()
    if is_country_only_location(location, country_code):
        centroid = country_centroid(country_code)
        if centroid:
            log.info("Ubicación %r solo indica el país: se usa su centro", location)
            return centroid
    if location:
        # Si viene como "Ciudad, País" (formato habitual del extractor), probar antes
        # una consulta estructurada. Una búsqueda libre puede confundir la ciudad con
        # una calle homónima situada en otra región del mismo país.
        head = location.split(",")[0].strip()
        if head and head != location:
            coords = _nominatim_city(head, country_code)
            if coords:
                log.info("Geocodificado como ciudad %r -> %s", head, coords)
                return coords

        query = f"{location}, {country_code}" if country_code else location
        coords = _nominatim(query, country_code)
        if coords:
            log.info("Geocodificado %r -> %s", query, coords)
            return coords
        # El texto puede ser demasiado específico ("Manjirón, Sierra Norte de Madrid"):
        # se reintenta solo con la primera parte antes de rendirse al centroide.
        if head and head != location:
            coords = _nominatim(f"{head}, {country_code}" if country_code else head, country_code)
            if coords:
                log.info("Geocodificado (recortado) %r -> %s", head, coords)
                return coords

    centroid = country_centroid(country_code)
    if centroid:
        log.info("Sin ciudad para %r: se usa el centro de %s", location, country_code)
        return centroid

    # El país no está en la tabla local (destino fuera de los habituales de Erasmus+):
    # se pregunta por el país a Nominatim antes de rendirse. Sabiendo el país, quedarse
    # sin pin sería tirar información que sí tenemos.
    if country_code:
        coords = _nominatim_country(country_code)
        if coords:
            log.info("País %s fuera de la tabla: geocodificado a %s", country_code, coords)
            return coords

    log.warning("Sin coordenadas para location=%r country=%r", location, country_code)
    return None
