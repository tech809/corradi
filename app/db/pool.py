"""Pool de conexiones async a Postgres con el tipo vector (pgvector) registrado."""
from __future__ import annotations

from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from app.config import cfg

_pool: AsyncConnectionPool | None = None


async def _configure(conn) -> None:
    await register_vector_async(conn)


def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            cfg.database_url,
            open=False,
            min_size=1,
            max_size=5,
            configure=_configure,
        )
    return _pool


async def open_pool() -> None:
    await get_pool().open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
