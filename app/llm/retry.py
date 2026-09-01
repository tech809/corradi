"""Reintentos con backoff para errores de Gemini.

  - 5xx transitorios (503 'high demand'…): reintento con backoff exponencial.
  - 429 RESOURCE_EXHAUSTED (cupo de peticiones por minuto del modelo): en llamadas de
    fondo (attempts > 2) se reintenta 2 veces con una espera larga (~35 s), porque la
    ventana del cupo es de 60 s; en llamadas interactivas (attempts <= 2, p.ej. el chat)
    NO se espera — se falla rápido con un aviso claro.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

log = logging.getLogger("corradi.llm")
T = TypeVar("T")

# Sin emoji: quien enseña el error (bot, alerts.alert…) ya antepone su propio "⚠️".
_QUOTA_HINT = "Problema de cuota: espera menos de 60 s y vuelve a intentarlo, debería funcionar."
_QUOTA_WAIT_S = 35


def _is_quota_error(e: Exception) -> bool:
    return getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e)


def with_retry(fn: Callable[[], T], attempts: int = 4, base: float = 1.0) -> T:
    from google.genai import errors as gerr

    last: Exception | None = None
    quota_left = 2 if attempts > 2 else 0   # el chat (attempts=2) no espera 35 s
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
        except gerr.ClientError as e:  # 4xx
            if not _is_quota_error(e):
                raise
            if quota_left <= 0:
                log.warning("Gemini 429 (cuota por minuto), sin más reintentos: %s", e)
                raise RuntimeError(f"{_QUOTA_HINT}\n\n{e}") from e
            quota_left -= 1
            last = e
            log.warning("Gemini 429 (cuota por minuto); espero %ss y reintento", _QUOTA_WAIT_S)
            time.sleep(_QUOTA_WAIT_S)
    assert last is not None
    raise last
