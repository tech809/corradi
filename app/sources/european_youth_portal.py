"""Cliente y normalización del catálogo oficial del Cuerpo Europeo de Solidaridad."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Any

import httpx

SEARCH_URL = "https://youth.europa.eu/api/rest/eyp/v1/search_en"
DETAIL_URL = "https://youth.europa.eu/solidarity/opportunity/{id}_en"
USER_AGENT = "CorradiBot/1.0 (+https://proactivefuture.eu)"

TOPICS = {
    "cata": "prevención y recuperación ante desastres", "citzn": "ciudadanía y participación",
    "cult": "creatividad y cultura", "discr": "lucha contra la discriminación",
    "distr": "preparación ante desastres", "edu": "educación y formación",
    "health": "salud y bienestar", "hygn": "agua, saneamiento e higiene",
    "job": "empleo y emprendimiento", "migr": "refugiados y migración",
    "natr": "medioambiente y naturaleza", "nutri": "nutrición y agricultura",
    "relief": "ayuda tras desastres", "shltr": "refugio", "sme": "apoyo a pymes",
    "socl": "retos sociales", "sprt": "deporte",
}


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


class _TextExtractor(HTMLParser):
    """Convierte el HTML editorial de EYP en texto legible y seguro."""

    _BLOCKS = {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "ul", "ol"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.suppressed += 1
        elif not self.suppressed and tag == "li":
            self.parts.append("\n• ")
        elif not self.suppressed and (tag == "br" or tag in self._BLOCKS):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        elif not self.suppressed and (tag == "li" or tag in self._BLOCKS):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data)


def _plain(value: str | None) -> str | None:
    if not value:
        return None
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts)
    # EYP suele guardar listas como un único párrafo: "Intro: - Uno - Dos".
    # Solo lo reinterpretamos cuando hay varios separadores para no romper guiones normales.
    text = "\n".join(
        line.replace(" - ", "\n• ") if line.count(" - ") >= 2 else line
        for line in text.splitlines()
    )
    lines = []
    for line in text.splitlines():
        clean = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if clean:
            lines.append(clean)
    return "\n".join(lines) or None


async def fetch_open(client: httpx.AsyncClient, today: date) -> list[dict[str, Any]]:
    params = {
        "type": "Opportunity", "size": "3000", "from": "0", "filters[status]": "open",
        "filters[date_end][operator]": ">=", "filters[date_end][value]": today.isoformat(),
        "filters[date_end][type]": "must",
    }
    response = await client.get(
        SEARCH_URL, params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                 "Referer": "https://youth.europa.eu/go-abroad/volunteering/opportunities_en"},
        timeout=45, follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    total = payload.get("hits", {}).get("total", {}).get("value", 0)
    hits = payload.get("hits", {}).get("hits", [])
    if total > len(hits):
        raise RuntimeError(f"EYP devolvió un catálogo incompleto ({len(hits)}/{total})")
    return [hit.get("_source", {}) for hit in hits]


def select_candidates(
    rows: list[dict[str, Any]], now: datetime, latest_deadline: date,
) -> list[dict[str, Any]]:
    """Selección conservadora: España, deadline explícita, inicio futuro y máximo 3 meses."""
    selected = []
    for row in rows:
        deadline, start = _dt(row.get("date_application_end")), _dt(row.get("date_start"))
        programme = row.get("funding_programme") or {}
        if not (
            row.get("status") == "open"
            and row.get("is_esc_related") is True
            and programme.get("is_volunteering") is True
            and "ES" in (row.get("volunteer_countries") or [])
            and deadline and deadline > now and deadline.date() <= latest_deadline
            and start and start > now
        ):
            continue
        selected.append(row)
    return selected


def to_project(row: dict[str, Any], checked_at: datetime) -> dict[str, Any]:
    deadline = _dt(row["date_application_end"])
    start, end = _dt(row.get("date_start")), _dt(row.get("date_end"))
    source_url = DETAIL_URL.format(id=row["id"])
    description = _plain(row.get("description"))
    countries = row.get("volunteer_countries") or []
    topic_codes = row.get("topics") or row.get("esc_topics") or []
    geo = row.get("geocode") or {}
    humanitarian = bool((row.get("funding_programme") or {}).get("is_humanitarian"))
    duration_days = (end.date() - start.date()).days + 1 if start and end else None
    duration_months = round(duration_days / 30.44, 1) if duration_days else None
    return {
        "title": _plain(row.get("title")) or "Voluntariado del Cuerpo Europeo de Solidaridad",
        "type": "VOLUNTEERING",
        "topic": ", ".join(TOPICS.get(code, code) for code in topic_codes) or None,
        "organiser_name": _plain(row.get("organisation_name")),
        "summary": description[:500] if description else None,
        "raw_message": description or source_url,
        "country_code": row.get("country"),
        "location": _plain(", ".join(x for x in (row.get("town"), row.get("country")) if x)),
        "latitude": float(geo["lat"]) if geo.get("lat") else None,
        "longitude": float(geo["lon"]) if geo.get("lon") else None,
        "start_date": start.date() if start else None,
        "end_date": end.date() if end else None,
        "duration_days": duration_days,
        "duration_months": duration_months,
        "application_deadline": deadline.date(),
        "application_deadline_at": deadline,
        "deadline_estimated": False,
        "infopack_url": source_url,
        "application_url": source_url,
        "participant_min_age": 18,
        "participant_max_age": 35 if humanitarian else 30,
        "detailed_description": description,
        "participant_profile": _plain(row.get("participant_profile")),
        "accommodation_details": _plain(row.get("boarding_arrangements")),
        "eligibility_countries": ", ".join(countries),
        "eligibility_country_codes": countries,
        "eligibility_scope": "explicit",
        "status": "open",
        "source": "eyp",
        "source_external_id": str(row["id"]),
        "source_url": source_url,
        "source_checked_at": checked_at,
        "publication_scope": "web",
    }
