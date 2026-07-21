"""Reintentos con backoff exponencial para errores transitorios de Gemini (503, 5xx)."""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

log = logging.getLogger("corradi.llm")
T = TypeVar("T")


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
    assert last is not None
    raise last
