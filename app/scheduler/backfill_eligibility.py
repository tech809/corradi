"""Rellena la elegibilidad estructurada de fichas anteriores a la migración 0020."""
from __future__ import annotations

import asyncio

from app.db import repository
from app.db.pool import close_pool, open_pool


async def run() -> int:
    await open_pool()
    updated = 0
    try:
        for row in await repository.list_open():
            if row.get("eligibility_country_codes"):
                continue
            await repository.update_project(
                row["identifier"],
                {"eligibility_countries": row.get("eligibility_countries")},
            )
            updated += 1
    finally:
        await close_pool()
    return updated


if __name__ == "__main__":
    print(asyncio.run(run()))
