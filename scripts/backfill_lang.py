"""Backfill puntual: traduce a español el `topic` y el `summary` de las oportunidades
ABIERTAS que estén en inglés. Deja títulos y nombres propios como están, y respeta términos
en inglés cuando su traducción quede forzada. Idempotente: lo ya en español vuelve igual.

Uso (dentro del contenedor bot, con GEMINI_API_KEY y BD accesibles):
    docker exec -i corradi-bot python -m scripts.backfill_lang
"""
from __future__ import annotations

import asyncio
import json

from google import genai
from google.genai import types

from app.config import cfg
from app.db import repository as repo
from app.db.pool import close_pool, get_pool, open_pool

PROMPT = """Traduce al español (castellano) los campos "topic" y "summary" de esta oportunidad.
Reglas:
- Si ya están en español, devuélvelos IGUAL.
- No traduzcas nombres propios, títulos de proyecto ni las claves "youth exchange",
  "training course", "ECS".
- En "topic" (lista de temáticas separadas por comas) puedes dejar un término en inglés SOLO
  si su traducción al español suena forzada o cutre; el resto, en español.
- "summary": 1-2 frases naturales en español.
Devuelve SOLO un JSON: {"topic": "...", "summary": "..."}.

topic: __TOPIC__
summary: __SUMMARY__
"""


def translate(client, topic, summary):
    p = PROMPT.replace("__TOPIC__", topic or "").replace("__SUMMARY__", summary or "")
    resp = client.models.generate_content(
        model=cfg.llm_model, contents=p,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(resp.text)


async def main():
    await open_pool()
    client = genai.Client(api_key=cfg.gemini_api_key)
    try:
        rows = await repo.list_open()
        print(f"{len(rows)} oportunidades abiertas")
        for o in rows:
            try:
                out = await asyncio.to_thread(translate, client, o.get("topic"), o.get("summary"))
            except Exception as e:  # noqa: BLE001
                print(f"  {o['identifier']}: ERROR {e}")
                continue
            topic, summary = out.get("topic"), out.get("summary")
            if topic == o.get("topic") and summary == o.get("summary"):
                print(f"  {o['identifier']}: sin cambios")
                continue
            async with get_pool().connection() as conn:
                await conn.execute(
                    "UPDATE projects SET topic = %s, summary = %s, updated = now() WHERE id = %s",
                    (topic, summary, o["id"]),
                )
            print(f"  {o['identifier']}: actualizado")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
