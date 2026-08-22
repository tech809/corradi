"""Clasificación + extracción de campos. Proveedor Gemini, o 'fake' para dry-run/tests."""
from __future__ import annotations

import json
import logging
import queue
from datetime import date

from app.config import cfg
from app.domain.project import normalize
from app.llm.prompts import CORRECTIONS_TEMPLATE, EXTRACTION_PROMPT, INFOPACK_ENRICHMENT_PROMPT

log = logging.getLogger("corradi.extractor")

_client = None

# Mismos precios que app/llm/chat.py (duplicado a propósito: son dos módulos independientes,
# y esto es solo un par de líneas -- ver docs/chatbot_mapa.md §3 para la fuente de precios).
_PRICES_USD_PER_1M = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
}
_DEFAULT_PRICE = _PRICES_USD_PER_1M["gemini-2.5-flash-lite"]

# extract() corre en un hilo aparte (pipeline.py lo llama vía asyncio.to_thread, porque el
# SDK de Gemini es síncrono) -- no puede hacer `await` a un repo async directamente. En vez
# de eso, deja el coste de cada llamada en esta cola thread-safe; quien llamó a extract()
# desde el lado async (pipeline.py) drena la cola con `flush_usage()` justo después.
_usage_queue: "queue.Queue[float]" = queue.Queue()


def _cost_usd(usage) -> float:
    if usage is None:
        return 0.0
    in_price, out_price = _PRICES_USD_PER_1M.get(cfg.llm_model, _DEFAULT_PRICE)
    prompt_tok = getattr(usage, "prompt_token_count", None) or 0
    out_tok = getattr(usage, "candidates_token_count", None) or 0
    return (prompt_tok * in_price + out_tok * out_price) / 1_000_000


async def flush_usage() -> None:
    """Vacía lo que `extract()` haya ido dejando en la cola desde la última vez y lo suma al
    gasto del mes en curso (`extraction_usage`). Llamar justo después de cada
    `await asyncio.to_thread(extractor.extract, ...)` -- barato si la cola está vacía."""
    total = 0.0
    count = 0
    while True:
        try:
            total += _usage_queue.get_nowait()
            count += 1
        except queue.Empty:
            break
    if count == 0:
        return
    from app.db import repository as repo
    month = date.today().strftime("%Y-%m")
    await repo.add_extraction_usage(month, total, count)


class LLMNotConfigured(RuntimeError):
    pass


def _gemini_client():
    """Cliente Gemini perezoso: solo importa google-genai si se usa de verdad."""
    global _client
    if _client is None:
        if not cfg.gemini_api_key:
            raise LLMNotConfigured("Falta GEMINI_API_KEY en el entorno (.env).")
        from google import genai
        _client = genai.Client(api_key=cfg.gemini_api_key)
    return _client


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.startswith("json"):
            text = text[4:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _corrections_block(corrections: list[str] | None) -> str:
    """Bloque de correcciones para el prompt (vacío si no hay). Se usa tanto en la
    confirmación previa a publicar ('Modificar') como al editar una ya publicada."""
    if not corrections:
        return ""
    items = "\n".join(f"- {c.strip()}" for c in corrections if c and c.strip())
    if not items:
        return ""
    return CORRECTIONS_TEMPLATE.replace("__CORRECTION_LIST__", items)


def extract(raw_text: str, ref_day: date | None = None, corrections: list[str] | None = None) -> dict:
    """Devuelve {is_opportunity: False, reason} o un dict de campos normalizados listo para la BD.

    `corrections`: instrucciones del coordinador para ajustar la extracción (p.ej. "la fecha
    de fin es el 20 de septiembre"). Se aplican SOBRE el mensaje original; `raw_message` se
    guarda siempre limpio (solo el texto original), para que la deduplicación no se vea afectada.
    """
    if cfg.llm_provider == "fake":
        from app.llm import fake
        return fake.extract(raw_text, ref_day, corrections)

    from google.genai import types

    from app.llm.retry import with_retry

    ref_day = ref_day or date.today()
    prompt = (
        EXTRACTION_PROMPT
        .replace("__TODAY__", ref_day.isoformat())
        .replace("__MESSAGE__", raw_text.strip())
        .replace("__CORRECTIONS__", _corrections_block(corrections))
    )
    resp = with_retry(lambda: _gemini_client().models.generate_content(
        model=cfg.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    ))
    try:
        _usage_queue.put_nowait(_cost_usd(getattr(resp, "usage_metadata", None)))
    except Exception:  # noqa: BLE001
        log.warning("No pude registrar el coste de esta llamada de extracción", exc_info=True)
    # strict=False: Gemini a veces copia texto del mensaje original con saltos de línea o
    # tabs sin escapar dentro de un valor de cadena (p.ej. un `summary` largo) -- eso es JSON
    # inválido en modo estricto ("Invalid control character...") aunque el contenido en sí
    # sea perfectamente válido. Permitir caracteres de control dentro de las cadenas evita
    # tirar la extracción entera por un salto de línea de más.
    fields = json.loads(_strip_fences(resp.text), strict=False)

    if isinstance(fields, list):
        # El mensaje traía varias oportunidades a la vez (no soportado: se procesan de una
        # en una). Se pide reenviarlas por separado en vez de fallar con un error críptico.
        return {
            "is_opportunity": False,
            "reason": "El mensaje parece incluir varias oportunidades a la vez. "
                      "Mándalas en mensajes separados, una por una.",
        }

    if not fields.get("is_opportunity"):
        return {"is_opportunity": False, "reason": fields.get("reason")}

    fields = normalize(
        fields, ref_day, cfg.default_deadline_days,
        raw_text=raw_text, last_minute_deadline_days=cfg.last_minute_deadline_days,
        max_deadline_months=cfg.max_deadline_months,
    )
    fields["is_opportunity"] = True
    fields["raw_message"] = raw_text.strip()   # limpio, sin las correcciones
    return fields


def enrich_from_infopack(fields: dict) -> dict:
    """Completa campos editoriales desde el infopack; conserva la extracción si falla."""
    if cfg.llm_provider == "fake" or not fields.get("infopack_url"):
        return fields
    from google.genai import types
    from app.llm.infopack import read
    from app.llm.retry import with_retry

    text = read(fields["infopack_url"])
    if not text:
        return fields
    context = {k: fields.get(k) for k in (
        "title", "summary", "type", "topic", "location", "start_date", "end_date",
        "participant_min_age", "participant_max_age", "cost",
    )}
    prompt = (INFOPACK_ENRICHMENT_PROMPT
              .replace("__FIELDS__", json.dumps(context, default=str, ensure_ascii=False))
              .replace("__INFOPACK__", text))
    try:
        resp = with_retry(lambda: _gemini_client().models.generate_content(
            model=cfg.llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
        ))
        _usage_queue.put_nowait(_cost_usd(getattr(resp, "usage_metadata", None)))
        enriched = json.loads(_strip_fences(resp.text), strict=False)
        out = dict(fields)
        for key in (
            "detailed_description", "programme_details", "learning_outcomes",
            "participant_profile", "accommodation_details", "covered_costs",
            "travel_details", "eligibility_countries",
        ):
            if enriched.get(key):
                out[key] = enriched[key]
        out["infopack_enriched"] = True
        return out
    except Exception:  # noqa: BLE001 - la publicación no depende del enriquecimiento
        log.warning("No pude enriquecer el infopack %s", fields.get("infopack_url"), exc_info=True)
        return fields
