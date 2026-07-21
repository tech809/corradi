"""API FastAPI: catálogo de oportunidades (lectura) sobre la BD."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query

from app.api.twilio_webhook import router as twilio_router
from app.db import repository as repo
from app.db.pool import close_pool, open_pool

_HIDDEN = {"embedding", "raw_message"}


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k in _HIDDEN:
            continue
        if isinstance(v, (UUID,)):
            out[k] = str(v)
        elif isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(title="CORRADI-BOT API", version="0.1.0", lifespan=lifespan)
app.include_router(twilio_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/opportunities")
async def list_opportunities(
    q: str | None = None,
    type: str | None = None,
    country: str | None = None,
    topic: str | None = None,
    only_open: bool = True,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    rows = await repo.search(q=q, type_=type, country=country, topic=topic, only_open=only_open, limit=limit)
    return {"count": len(rows), "results": [_serialize(r) for r in rows]}


@app.get("/opportunities/{identifier}")
async def get_opportunity(identifier: str) -> dict[str, Any]:
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return _serialize(row)
