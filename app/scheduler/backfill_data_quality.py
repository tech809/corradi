"""Re-aplica a las fichas ABIERTAS ya guardadas las correcciones de calidad de datos que
las nuevas ya reciben al entrar (ver `app.domain.project` y `app.sources.european_youth_portal`):

  1. deadline ESTIMADA que cae el día de inicio o después → día anterior al inicio
     (nunca antes de hoy);
  2. resúmenes EYP cortados a mitad de frase → se recalculan desde la descripción completa
     cortando en frase/palabra y sin relleno tipo "See full description… here.";
  3. temáticas con códigos numéricos ('235', '253') → se quitan;
  4. títulos que son un código de proyecto o van en MAYÚSCULAS → título derivado /
     tipo título conservando siglas.

En fichas no-EYP cuyo título cambia, también se recalcula el hash de deduplicación (si era
el derivado del título y el nuevo no está ya en uso), para que un reenvío del mismo mensaje
se siga detectando como duplicado.

Se ejecuta a mano una sola vez:
    python -m app.scheduler.backfill_data_quality            # simulación: muestra qué cambiaría
    python -m app.scheduler.backfill_data_quality --apply    # lo aplica
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.project import (
    _TITLE_FALLBACK_PREFIX, cap_estimated_deadline, cap_summary, clean_title, clean_topic,
    make_hash,
)
from app.sources import european_youth_portal as eyp

log = logging.getLogger("corradi.backfill_data_quality")

_COLUMNS = (
    "id, identifier, source, title, topic, summary, detailed_description, organiser_name, "
    "location, type, country_code, hash, deadline_estimated, start_date, application_deadline"
)


def compute_changes(row: dict[str, Any], today: date) -> dict[str, Any]:
    """Campos que cambiarían en esta fila (solo los que difieren). Lógica pura, sin BD."""
    changes: dict[str, Any] = {}
    is_eyp = row.get("source") == "eyp"
    town = (row.get("location") or "").split(",")[0].strip() or None

    if is_eyp:
        title = clean_title(row.get("title"), organiser=row.get("organiser_name"), town=town,
                            fallback_prefix="Voluntariado ESC", default=eyp.DEFAULT_TITLE)
    else:
        title = clean_title(
            row.get("title"), organiser=row.get("organiser_name"),
            fallback_prefix=_TITLE_FALLBACK_PREFIX.get(row.get("type"), "Proyecto Erasmus+"),
        )
    if title and title != row.get("title"):
        changes["title"] = title

    topic = clean_topic(row.get("topic"))
    if topic != row.get("topic"):
        changes["topic"] = topic

    if is_eyp:
        summary = cap_summary(row.get("detailed_description") or row.get("summary"),
                              eyp.SUMMARY_MAX_LEN)
        if summary != row.get("summary"):
            changes["summary"] = summary

    deadline, start = row.get("application_deadline"), row.get("start_date")
    if row.get("deadline_estimated") and deadline and start:
        capped = cap_estimated_deadline(deadline, start, today)
        if capped < deadline:
            changes["application_deadline"] = capped
    return changes


async def run(apply: bool = False) -> None:
    from app.config import cfg
    from app.db.pool import close_pool, get_pool, open_pool

    today = datetime.now(ZoneInfo(cfg.timezone)).date()
    await open_pool()
    try:
        async with get_pool().connection() as conn:
            cur = await conn.execute(f"SELECT {_COLUMNS} FROM projects WHERE status = 'open'")
            names = [d.name for d in cur.description]
            rows = [dict(zip(names, r)) for r in await cur.fetchall()]
            cur = await conn.execute("SELECT hash FROM projects")
            used_hashes = {r[0] for r in await cur.fetchall()}

        plan = []
        for row in rows:
            changes = compute_changes(row, today)
            if not changes:
                continue
            # Rehash solo si el hash actual era el derivado del título (no los 'eyp:<id>' ni
            # otros especiales) y el nuevo no colisiona con otra fila (columna UNIQUE).
            if "title" in changes and row.get("source") != "eyp":
                old_hash = make_hash(row["title"], row.get("country_code"), row.get("start_date"))
                new_hash = make_hash(changes["title"], row.get("country_code"), row.get("start_date"))
                if row["hash"] == old_hash and new_hash not in used_hashes:
                    changes["hash"] = new_hash
                    used_hashes.add(new_hash)
            plan.append((row, changes))

        counts: dict[str, int] = {}
        for row, changes in plan:
            log.info("%s · %s", row["identifier"], (row.get("title") or "")[:60])
            for key, new in changes.items():
                counts[key] = counts.get(key, 0) + 1
                if key == "hash":
                    continue
                old = row.get(key)
                if key == "summary":
                    log.info("    summary: …%r → …%r", (old or "")[-60:], (new or "")[-60:])
                else:
                    log.info("    %s: %r → %r", key, old, new)
        log.info("%s de %s fichas abiertas con cambios; por campo: %s", len(plan), len(rows), counts)

        if not apply:
            log.info("Simulación (sin --apply): no se ha tocado nada.")
            return

        async with get_pool().connection() as conn:
            for row, changes in plan:
                sets = ", ".join(f"{key} = %s" for key in changes)
                await conn.execute(
                    f"UPDATE projects SET {sets}, updated = now() WHERE id = %s",
                    (*changes.values(), row["id"]),
                )
        log.info("Aplicado: %s fichas actualizadas.", len(plan))
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="solo muestra qué cambiaría (por defecto)")
    mode.add_argument("--apply", action="store_true", help="escribe los cambios en la BD")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run(apply=args.apply))
