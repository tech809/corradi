"""Reintentos con backoff exponencial para errores transitorios de Gemini (503, 5xx).

El 429 (RESOURCE_EXHAUSTED — límite de peticiones por minuto del modelo) NO se reintenta
aquí: la ventana del cupo es de 60 s y esto puede ser una petición web síncrona. Solo se
le antepone un aviso claro al mensaje de error para quien lo vea.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

log = logging.getLogger("corradi.llm")
T = TypeVar("T")

_QUOTA_HINT = (
    "⚠️ Problema de cuota: espera menos de 60 s y vuelve a intentarlo, debería funcionar."
)


def _is_quota_error(e: Exception) -> bool:
    return getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e)


def with_retry(fn: Callable[[], T], attempts: int = 4, base: float = 1.0) -> T:
    from google.genai import errors as gerr

    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except gerr.ServerError as e:  # 5xx transitorios (p.ej. 503 'high demand')
            last = e
            if i == attempts - 1:
                raise
            wait = base * (2 ** i)
            log.warning("Gemini %s; reintento %d/%d en %.1fs", e, i + 1, attempts - 1, wait)
            time.sleep(wait)
        except gerr.ClientError as e:  # 4xx — no se reintenta
            if _is_quota_error(e):
                log.warning("Gemini 429 (cuota por minuto): %s", e)
                raise RuntimeError(f"{_QUOTA_HINT}\n\n{e}") from e
            raise
    assert last is not None
    raise last
