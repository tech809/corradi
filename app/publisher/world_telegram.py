"""English Telegram formatting shared by the two Corradi World bots."""
from __future__ import annotations

import html
from datetime import date
from typing import Any


def _flag(code: str | None) -> str:
    code = (code or "").upper()
    return "".join(chr(127397 + ord(c)) for c in code) if len(code) == 2 and code.isalpha() else "🌍"


def _date(value) -> str:
    if not value:
        return "to be confirmed"
    if isinstance(value, date):
        value = value.isoformat()
    year, month, day = (int(part) for part in str(value).split("-")[:3])
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{day} {months[month - 1]} {year}"


def format_opportunity(opp: dict[str, Any], include_source: bool = True) -> str:
    e = lambda value: html.escape(str(value or ""))
    lines = [f"{_flag(opp.get('country_code'))} <b>{e(opp.get('title') or 'Training opportunity')}</b>"]
    if opp.get("topic"):
        lines.append(f"🎯 {e(opp['topic'])}")
    if opp.get("location"):
        lines.append(f"📍 {e(opp['location'])}")
    if opp.get("start_date") or opp.get("end_date"):
        lines.append(f"🗓 {_date(opp.get('start_date'))} — {_date(opp.get('end_date'))}")
    if opp.get("application_deadline"):
        lines.append(f"⏳ Apply by <b>{_date(opp['application_deadline'])}</b>")
    if opp.get("eligibility_countries"):
        lines.extend(["", f"🌍 <b>Eligible residents:</b> {e(opp['eligibility_countries'])}"])
    if opp.get("summary"):
        lines.extend(["", e(opp["summary"])])
    links = []
    if str(opp.get("application_url") or "").startswith(("https://", "http://")):
        links.append(f'<a href="{e(opp["application_url"])}">Apply →</a>')
    if str(opp.get("infopack_url") or "").startswith(("https://", "http://")):
        links.append(f'<a href="{e(opp["infopack_url"])}">Infopack →</a>')
    if include_source and opp.get("source_url"):
        links.append(f'<a href="{e(opp["source_url"])}">SALTO source →</a>')
    if links:
        lines.extend(["", " · ".join(links)])
    return "\n".join(lines)
