"""Demo offline del flujo completo SIN base de datos ni claves.

Fuerza el proveedor 'fake' y procesa los mensajes de ejemplo: clasifica, extrae,
deduplica (en memoria) y muestra cómo quedarían publicados en Telegram y en WhatsApp.

    python -m app.demo
"""
from __future__ import annotations

import os

os.environ.setdefault("LLM_PROVIDER", "fake")  # debe fijarse antes de importar la config

import math

from app.llm import embeddings, extractor  # noqa: E402
from app.publisher import telegram_publisher as pub  # noqa: E402
from app.samples import SAMPLE_MESSAGES  # noqa: E402
from app.config import cfg  # noqa: E402
from app.domain.project import make_hash  # noqa: E402


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def main() -> None:
    print(f"== DEMO (proveedor LLM: {cfg.llm_provider}, umbral dedup: {cfg.dedup_threshold}) ==\n")
    seen: list[tuple[str, list[float], dict]] = []  # (hash, vector, fields)
    seq = 0

    for i, msg in enumerate(SAMPLE_MESSAGES, start=1):
        print(f"\n{'─'*70}\n[Mensaje {i}]")
        fields = extractor.extract(msg)

        if not fields.get("is_opportunity"):
            print(f"  ❌ Descartado (no es oportunidad): {fields.get('reason')}")
            continue

        h = make_hash(fields.get("title"), fields.get("country_code"), fields.get("start_date"))
        vec = embeddings.embed(msg)

        if any(h == sh for sh, _, _ in seen):
            print("  ♻️  Duplicado exacto (hash título+país+fecha) — no se publica.")
            continue
        best, match = max(((_cosine(vec, sv), sf) for _, sv, sf in seen), default=(0.0, None))
        if match is not None:
            print(f"  🔎 Similitud con la más parecida («{match['title']}»): {best:.0%}")
        if best >= cfg.dedup_threshold:
            print(f"  ♻️  Supera el umbral ({cfg.dedup_threshold:.0%}) — no se publica.")
            continue

        seq += 1
        fields["identifier"] = f"{cfg.identifier_prefix}-2026-{seq:04d}"
        seen.append((h, vec, fields))

        print("  ✅ Nueva oportunidad. Así se publicaría:\n")
        print("  ── Telegram ──")
        print("    " + pub.format_opportunity(fields).replace("\n", "\n    "))
        print("\n  ── WhatsApp (handoff) ──")
        print("    " + pub.format_opportunity_whatsapp(fields).replace("\n", "\n    "))

    print(f"\n{'='*70}\nResumen diario que se publicaría:\n")
    print(pub.format_daily_summary([f for _, _, f in seen]))
    print(
        "\nNota: el proveedor 'fake' usa un embedding bag-of-words que infravalora los "
        "casi-duplicados (el mensaje 3 puntúa ~70%). Con embeddings reales de Gemini los "
        "casi-duplicados superan el umbral y se deduplican; el repost exacto (mensaje 6) se "
        "captura siempre por hash."
    )


if __name__ == "__main__":
    main()
