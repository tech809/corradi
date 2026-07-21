"""Proveedor LLM 'fake' para dry-run y tests: extracción heurística + embeddings deterministas.

Activado con LLM_PROVIDER=fake. No necesita claves ni red, así que permite ver el flujo
completo (clasificar → extraer → deduplicar → formatear) sin tokens de Gemini.
"""
from __future__ import annotations

import hashlib
import re
import struct
from datetime import date

from app.config import cfg
from app.domain.project import normalize

_COUNTRIES = {
    "spain": "ES", "españa": "ES", "espana": "ES", "italy": "IT", "italia": "IT",
    "portugal": "PT", "greece": "GR", "grecia": "GR", "romania": "RO", "rumania": "RO",
    "rumanía": "RO", "france": "FR", "francia": "FR", "germany": "DE", "alemania": "DE",
    "poland": "PL", "polonia": "PL", "croatia": "HR", "croacia": "HR",
}
_TYPE_HINTS = {
    "YOUTH_EXCHANGE": ["youth exchange", "intercambio", "ye "],
    "TRAINING_COURSE": ["training course", "curso de formaci", "tc "],
    "VOLUNTEERING": ["volunteer", "voluntariado", "esc ", "solidarity corps"],
    "WORKSHOP": ["workshop", "taller"],
}
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_URL_RE = re.compile(r"https?://\S+")


def extract(raw_text: str, ref_day: date | None = None) -> dict:
    ref_day = ref_day or date.today()
    text = raw_text.strip()
    low = text.lower()

    if len(text) < 15 or low.startswith(("hola", "hi ", "gracias", "thanks")):
        return {"is_opportunity": False, "reason": "no parece una oportunidad (texto corto/saludo)"}

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = re.sub(r"[^\w\s&/áéíóúñÁÉÍÓÚ.-]", "", lines[0])
    title = re.sub(r"\s+", " ", title).strip()[:120] or "Oportunidad"

    dates = _DATE_RE.findall(text)
    start = dates[0] if dates else None
    end = dates[1] if len(dates) > 1 else None

    deadline = None
    m = re.search(r"(deadline|inscripci[oó]n|aplica|apply|l[ií]mite).{0,40}?(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
    if m:
        deadline = m.group(2)

    url_m = _URL_RE.search(text)
    country = next((code for name, code in _COUNTRIES.items() if re.search(rf"\b{name}\b", low)), None)
    ptype = next((t for t, hints in _TYPE_HINTS.items() if any(h in low for h in hints)), None)

    fields = {
        "title": title, "type": ptype, "topic": None, "summary": lines[0][:160],
        "country_code": country, "location": None,
        "start_date": start, "end_date": end, "application_deadline": deadline,
        "infopack_url": None, "application_url": url_m.group(0) if url_m else None,
        "max_participants": None, "participant_min_age": None, "participant_max_age": None,
        "cost": None, "contact_information": None,
    }
    fields = normalize(fields, ref_day, cfg.default_deadline_days)
    fields["is_opportunity"] = True
    fields["raw_message"] = text
    return fields


def embed(text: str) -> list[float]:
    """Embedding 'fake' por feature hashing de palabras (bag-of-words con signo).

    Determinista y, a diferencia de un hash del texto entero, da vectores PARECIDOS a
    textos con vocabulario parecido → la deduplicación semántica funciona en el demo.
    No sustituye a un embedding real (Gemini), pero ilustra el comportamiento.
    """
    dim = cfg.embed_dim
    vec = [0.0] * dim
    for tok in re.findall(r"\w+", text.lower()):
        h = struct.unpack("I", hashlib.md5(tok.encode()).digest()[:4])[0]
        vec[h % dim] += 1.0 if (h // dim) % 2 == 0 else -1.0
    return vec
