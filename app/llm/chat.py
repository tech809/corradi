"""Chat del mapa: responde en lenguaje natural sobre las oportunidades ABIERTAS ahora mismo.

Arquitectura "catálogo completo en el prompt" (docs/chatbot_mapa.md §2(a)): nada de RAG, se
mete el catálogo entero de `repo.list_open()` como texto compacto en cada consulta. El LLM
NUNCA escribe datos de una oportunidad: solo devuelve `ids`, y `ask()` valida cada uno contra
el conjunto real de abiertas antes de que salga de aquí — así es estructuralmente imposible
que se invente una oportunidad (§6, mitigación nº1 y nº2).

El gasto se mide DE VERDAD con `usage_metadata` de cada respuesta de Gemini (no se estima) y
se acumula en la tabla `chat_usage` (mes en curso). Al superar `cfg.chat_monthly_budget_usd`
el chat deja de llamar a Gemini hasta el mes siguiente, y se avisa una única vez a los admins
por Telegram vía `app.alerts.alert()`.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

from app.config import cfg
from app.db import repository as repo
from app.llm.prompts import CHAT_PROMPT

log = logging.getLogger("corradi.chat")

_client = None

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Precios reales de Gemini (USD por 1M tokens, tier de pago) — docs/chatbot_mapa.md §3,
# consultados 2026-07-27 en https://ai.google.dev/gemini-api/docs/pricing. Si `cfg.llm_model`
# apunta a un modelo que no está aquí, se usa flash-lite como aproximación conservadora (mejor
# una estimación de coste que un cálculo roto) y se avisa una vez por proceso en los logs.
_PRICES_USD_PER_1M = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
}
_DEFAULT_PRICE = _PRICES_USD_PER_1M["gemini-2.5-flash-lite"]
_warned_unknown_price = False

# Abreviaturas de tipo para el catálogo (ahorran tokens frente al nombre completo del enum;
# mismas etiquetas que ya usa el front en mapa.html, salvo VOLUNTEERING -> "ECS").
_TYPE_ABBR = {
    "YOUTH_EXCHANGE": "YE", "TRAINING_COURSE": "TC", "VOLUNTEERING": "ECS", "WORKSHOP": "WS",
}


class LLMNotConfigured(RuntimeError):
    pass


def _gemini_client():
    global _client
    if _client is None:
        if not cfg.gemini_api_key:
            raise LLMNotConfigured("Falta GEMINI_API_KEY en el entorno (.env).")
        from google import genai
        _client = genai.Client(api_key=cfg.gemini_api_key)
    return _client


def _strip_fences(text: str) -> str:
    """Idéntico a extractor._strip_fences (Gemini a veces envuelve el JSON en ```json ``` a
    pesar de response_mime_type). Se duplica esta función de 8 líneas en vez de crear un
    módulo compartido para algo tan pequeño."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.startswith("json"):
            text = text[4:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _next_month_label(month: str) -> str:
    y, m = (int(x) for x in month.split("-"))
    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"1 de {_MESES_ES[m2 - 1]}"


# ── Catálogo compacto (cacheado en memoria unos minutos, docs/chatbot_mapa.md §2(a)) ────
_catalog_cache: dict[str, Any] = {"text": None, "ids": frozenset(), "built_at": 0.0}


def _age_label(row: dict) -> str:
    lo, hi = row.get("participant_min_age"), row.get("participant_max_age")
    if lo is None and hi is None:
        return "edad no especificada"
    if lo is not None and hi is not None:
        return f"edad {lo}-{hi}"
    if lo is not None:
        return f"edad {lo}+"
    return f"edad hasta {hi}"


def _cost_label(row: dict) -> str:
    cost = row.get("cost")
    if cost is None:
        return "coste no especificado"
    try:
        value = float(cost)
    except (TypeError, ValueError):
        return "coste no especificado"
    return "gratis" if value == 0 else f"{value:g} €"


def _catalog_line(row: dict) -> str:
    place = ", ".join(x for x in (row.get("location"), row.get("country_code")) if x)
    if row.get("start_date") or row.get("end_date"):
        s = row["start_date"].isoformat() if row.get("start_date") else "?"
        e = row["end_date"].isoformat() if row.get("end_date") else "?"
        dates = f"{s}/{e}"
    else:
        dates = "fechas no especificadas"
    deadline = (
        f"cierra {row['application_deadline'].isoformat()}"
        if row.get("application_deadline") else "sin fecha límite de inscripción"
    )
    parts = [
        row["identifier"],
        row.get("title") or "",
        _TYPE_ABBR.get(row.get("type"), row.get("type") or "?"),
        place or "lugar no especificado",
        dates,
        deadline,
        _age_label(row),
        _cost_label(row),
        row.get("topic") or "",
    ]
    line = " | ".join(parts)
    summary = (row.get("summary") or "").strip()
    if summary:
        line += f"\n{summary}"
    return line


async def _get_catalog() -> tuple[str, frozenset]:
    now = time.monotonic()
    if _catalog_cache["text"] is not None and (now - _catalog_cache["built_at"]) < cfg.chat_catalog_cache_seconds:
        return _catalog_cache["text"], _catalog_cache["ids"]
    rows = await repo.list_open()
    text = "\n\n".join(_catalog_line(r) for r in rows)
    ids = frozenset(r["identifier"] for r in rows)
    _catalog_cache.update(text=text, ids=ids, built_at=now)
    return text, ids


def _cost_usd(usage) -> float:
    global _warned_unknown_price
    if usage is None:
        return 0.0
    prices = _PRICES_USD_PER_1M.get(cfg.llm_model)
    if prices is None:
        if not _warned_unknown_price:
            log.warning(
                "Sin precio conocido para el modelo '%s' — se usa el de flash-lite como "
                "aproximación para el gasto del chat.", cfg.llm_model,
            )
            _warned_unknown_price = True
        prices = _DEFAULT_PRICE
    in_price, out_price = prices
    prompt_tok = getattr(usage, "prompt_token_count", None) or 0
    out_tok = getattr(usage, "candidates_token_count", None) or 0
    return (prompt_tok * in_price + out_tok * out_price) / 1_000_000


async def _record_usage(resp) -> None:
    cost = _cost_usd(getattr(resp, "usage_metadata", None))
    month = _current_month()
    usage = await repo.add_chat_usage(month, cost)
    if usage["spent_usd"] >= cfg.chat_monthly_budget_usd and not usage["alerted"]:
        await repo.mark_chat_alerted(month)
        from app import alerts
        await alerts.alert(
            "Chatbot del mapa: presupuesto mensual agotado",
            f"Mes {month}: {usage['spent_usd']:.4f} $ gastados en {usage['queries']} consultas "
            f"(tope {cfg.chat_monthly_budget_usd} $). El chat deja de llamar a Gemini hasta "
            "que empiece el mes que viene.",
            key=f"chat_budget_{month}",
        )


async def status() -> dict[str, Any]:
    """Para GET /api/chat/status: permite al front decidir si muestra el formulario o el
    aviso ANTES de que el visitante escriba nada (no solo al fallar un envío)."""
    if cfg.llm_provider == "fake":
        return {"disponible": True, "motivo": None}
    month = _current_month()
    usage = await repo.get_chat_usage(month)
    spent = float(usage["spent_usd"]) if usage else 0.0
    if spent >= cfg.chat_monthly_budget_usd:
        return {
            "disponible": False,
            "motivo": f"Presupuesto de este mes agotado, vuelve el {_next_month_label(month)}",
        }
    return {"disponible": True, "motivo": None}


async def _ask_gemini(pregunta: str, catalogo: str) -> dict[str, Any]:
    from google.genai import types

    from app.llm.retry import with_retry

    prompt = (
        CHAT_PROMPT
        .replace("__TODAY__", date.today().isoformat())
        .replace("__CATALOGO__", catalogo)
        .replace("__PREGUNTA__", pregunta)
    )
    try:
        resp = with_retry(
            lambda: _gemini_client().models.generate_content(
                model=cfg.llm_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.2,
                    max_output_tokens=600,
                ),
            ),
            attempts=2,  # NO 4: esto es una petición web síncrona, no puede tardar ~15s de backoff
        )
    except Exception:
        log.exception("Fallo llamando a Gemini para el chat del mapa")
        return {
            "respuesta": "El asistente no está disponible ahora mismo — usa los filtros o el buscador.",
            "ids": [], "aviso": "fallo_temporal",
        }

    await _record_usage(resp)

    try:
        data = json.loads(_strip_fences(resp.text))
    except (json.JSONDecodeError, TypeError, AttributeError):
        log.warning("Respuesta de Gemini no era JSON válido: %r", getattr(resp, "text", None))
        return {
            "respuesta": "No he podido interpretar bien tu pregunta. Prueba a reformularla o usa los filtros.",
            "ids": [], "aviso": None,
        }
    if not isinstance(data, dict):
        return {
            "respuesta": "No he podido interpretar bien tu pregunta. Prueba a reformularla o usa los filtros.",
            "ids": [], "aviso": None,
        }
    return data


async def ask(pregunta: str) -> dict[str, Any]:
    """Devuelve SIEMPRE {respuesta, ids, aviso} (contrato de docs/chatbot_mapa.md §5).

    `ids` viene filtrado contra las oportunidades abiertas de verdad: si Gemini se inventa
    o alucina un identifier que no existe, desaparece aquí antes de llegar al front (§6)."""
    pregunta = (pregunta or "").strip()[:500]
    await repo.bump_chat_query_counter()

    if cfg.llm_provider != "fake":
        chat_status = await status()
        if not chat_status["disponible"]:
            return {"respuesta": chat_status["motivo"], "ids": [], "aviso": chat_status["motivo"]}

    catalogo, open_ids = await _get_catalog()
    if not open_ids:
        return {
            "respuesta": "Ahora mismo no hay ninguna oportunidad abierta. Vuelve a intentarlo más adelante.",
            "ids": [], "aviso": None,
        }

    if cfg.llm_provider == "fake":
        from app.llm import fake
        result = fake.chat(pregunta, open_ids)
    else:
        result = await _ask_gemini(pregunta, catalogo)

    ids = [i for i in (result.get("ids") or []) if i in open_ids]
    return {
        "respuesta": result.get("respuesta") or "",
        "ids": ids,
        "aviso": result.get("aviso"),
    }
