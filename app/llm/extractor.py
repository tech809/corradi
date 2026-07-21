"""Clasificación + extracción de campos. Proveedor Gemini, o 'fake' para dry-run/tests."""
from __future__ import annotations

import json
from datetime import date

from app.config import cfg
from app.domain.project import normalize
from app.llm.prompts import EXTRACTION_PROMPT

_client = None


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


def extract(raw_text: str, ref_day: date | None = None) -> dict:
    """Devuelve {is_opportunity: False, reason} o un dict de campos normalizados listo para la BD."""
    if cfg.llm_provider == "fake":
        from app.llm import fake
        return fake.extract(raw_text, ref_day)

    from google.genai import types

    from app.llm.retry import with_retry

    ref_day = ref_day or date.today()
    prompt = EXTRACTION_PROMPT.replace("__TODAY__", ref_day.isoformat()).replace("__MESSAGE__", raw_text.strip())
    resp = with_retry(lambda: _gemini_client().models.generate_content(
        model=cfg.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    ))
    fields = json.loads(_strip_fences(resp.text))

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

    fields = normalize(fields, ref_day, cfg.default_deadline_days)
    fields["is_opportunity"] = True
    fields["raw_message"] = raw_text.strip()
    return fields
