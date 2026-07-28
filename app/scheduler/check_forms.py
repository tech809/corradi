"""Comprobación diaria de que el formulario de inscripción (Google Forms, con diferencia
el caso más habitual) de cada oportunidad ABIERTA sigue aceptando respuestas.

Sin LLM, a petición expresa: para Google Forms, el propio Google da una señal 100%
fiable y gratis con una simple petición HTTP -- la URL final tras seguir redirecciones
acaba en "/closedform" cuando el organizador lo ha cerrado, y el cuerpo de esa página
dice "no longer accepting responses" -- comprobado en real (2026-07-29) contra
formularios abiertos y cerrados de verdad de la propia cola de producción.

Deliberadamente solo actúa sobre `application_url` que apunten a forms.gle o
docs.google.com/forms (la inmensa mayoría). El resto de dominios (Google Drive, webs
propias, Canva, bit.ly, Linktree...) se dejan fuera a propósito: distinguir "cerrado" de
"roto" ahí sin mirar contenido de verdad exigiría LLM o heurísticas mucho más frágiles,
justo lo que se pidió evitar. Parametrizable vía _GOOGLE_FORM_RE si algún día merece la
pena ampliarlo.

Si el formulario aparece cerrado, la oportunidad se cierra igual que si el coordinador
la hubiera cerrado a mano (`repo.close_project`) -- desaparece del mapa sola.

Ejecutar por cron en la EC2 (una vez al día):
    python -m app.scheduler.check_forms
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx

from app import alerts
from app.db import repository as repo
from app.db.pool import close_pool, open_pool

log = logging.getLogger("corradi.check_forms")

_GOOGLE_FORM_RE = re.compile(r"^https?://(forms\.gle|docs\.google\.com/forms)/", re.I)
_CLOSED_HINTS = (
    "no longer accepting responses",
    "ya no acepta respuestas",
    "ya no admite respuestas",
)


def _is_google_form(url: str | None) -> bool:
    return bool(url) and bool(_GOOGLE_FORM_RE.match(url))


async def _form_is_closed(client: httpx.AsyncClient, url: str) -> bool | None:
    """True/False si se pudo determinar con confianza, None si el formulario no
    respondió bien (red, 5xx...) -- un fallo de red no es lo mismo que un formulario
    cerrado de verdad, así que en ese caso NO se toca la oportunidad."""
    try:
        r = await client.get(url, timeout=15, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if r.status_code >= 500:
        return None
    if "closedform" in str(r.url):
        return True
    low = r.text.lower()
    return any(hint in low for hint in _CLOSED_HINTS)


async def run() -> None:
    await open_pool()
    try:
        opps = await repo.list_open()
        candidates = [o for o in opps if _is_google_form(o.get("application_url"))]
        if not candidates:
            log.info("Nada que comprobar (0 Google Forms entre %s oportunidades abiertas).", len(opps))
            return
        closed = checked = 0
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (compatible; CorradiBot/1.0)"}) as client:
            for o in candidates:
                result = await _form_is_closed(client, o["application_url"])
                checked += 1
                if result is True:
                    await repo.close_project(o["identifier"])
                    closed += 1
                    log.info("Formulario cerrado -> oportunidad cerrada: %s (%s)", o["identifier"], o["title"])
        log.info("Comprobación de formularios: %s revisados, %s cerrados de %s oportunidades abiertas.",
                  checked, closed, len(opps))
        if closed:
            await alerts.alert(
                "Formularios cerrados detectados",
                f"{closed} oportunidad(es) se han cerrado porque su Google Form ya no acepta respuestas.",
            )
    except Exception as e:  # noqa: BLE001
        log.exception("Falló la comprobación diaria de formularios")
        await alerts.alert("Falló la comprobación diaria de formularios", f"{type(e).__name__}: {e}")
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
