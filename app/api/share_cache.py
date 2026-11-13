"""Caché en disco de la tarjeta de GET /share/{id}/story.png.

Renderizarla cuesta segundos (descarga de la foto editorial + Pillow), y la app la pide
cada vez que alguien abre una ficha. La clave recoge TODO lo que cambia la imagen:

- los campos de la fila que lee `instagram_card._compose` (título, tipo, lugar, fechas,
  foto, países...) más `updated`, así cualquier edición de la ficha invalida la entrada;
- la etiqueta de plazo ("quedan 9 días" / "cierra mañana"...), que depende del día de hoy:
  en vez de meter la fecha, se mete la etiqueta, que solo cambia cuando cambia la imagen;
- formato y calidad de salida, y `RENDER_VERSION` (subirla si cambia el diseño).

Lo que la clave no ve (la foto remota cambió en origen, o falló su descarga y se usó la
de reserva) lo acota la caducidad `ttl_hours`. El ETag es la propia clave, así un 304 se
resuelve sin tocar el disco.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

log = logging.getLogger("corradi.share_cache")

# Subir si cambia el diseño de la tarjeta (instagram_card._compose) para invalidar todo.
RENDER_VERSION = "1"

# Campos de la fila que pinta la tarjeta (ver instagram_card._compose y _compact_dates).
_RENDER_FIELDS = (
    "identifier", "title", "type", "topic", "location", "country_code",
    "eligibility_countries", "image_url", "start_date", "end_date", "updated",
)

_EXT = {"jpeg": ".jpg", "png": ".png"}


def cache_key(row: dict[str, Any], pill_label: str, fmt: str, quality: int) -> str:
    payload = {f: row.get(f) for f in _RENDER_FIELDS}
    payload.update(_v=RENDER_VERSION, label=pill_label, fmt=fmt, q=quality if fmt == "jpeg" else None)
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def etag_for(key: str) -> str:
    return f'"{key[:32]}"'


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """If-None-Match puede traer varias etiquetas, débiles (W/"...") o "*"."""
    if not if_none_match:
        return False
    for tag in if_none_match.split(","):
        tag = tag.strip()
        if tag == "*" or tag.removeprefix("W/") == etag:
            return True
    return False


class ShareImageCache:
    def __init__(self, directory: str | Path, max_files: int, max_mb: int, ttl_hours: int) -> None:
        self.directory = Path(directory)
        self.max_files = max(1, max_files)
        self.max_bytes = max(1, max_mb) * 1024 * 1024
        self.ttl_seconds = max(0, ttl_hours) * 3600
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiters: dict[str, int] = {}
        self._inflight: dict[str, bytes] = {}
        self._disk_ok: bool | None = None

    def _usable(self) -> bool:
        if self._disk_ok is None:
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                self._disk_ok = os.access(self.directory, os.W_OK)
            except OSError:
                self._disk_ok = False
            if not self._disk_ok:
                log.warning("Caché de /share sin disco: %s no es escribible", self.directory)
        return self._disk_ok

    def _path(self, key: str, fmt: str) -> Path:
        return self.directory / f"{key}{_EXT.get(fmt, '.bin')}"

    def _read(self, path: Path) -> bytes | None:
        try:
            st = path.stat()
            if self.ttl_seconds and time.time() - st.st_mtime > self.ttl_seconds:
                return None
            return path.read_bytes()
        except OSError:
            return None

    def _write(self, path: Path, data: bytes) -> None:
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, path)  # atómico: nadie lee un fichero a medio escribir
        except OSError as exc:
            log.warning("No se pudo guardar %s en la caché de /share: %s", path.name, exc)
            tmp.unlink(missing_ok=True)
            return
        self._evict()

    def _evict(self) -> None:
        """Borra las entradas más viejas (por mtime) por encima de N ficheros o M bytes."""
        try:
            entries = []
            for p in self.directory.iterdir():
                if p.name.startswith(".") or not p.is_file():
                    continue
                st = p.stat()
                entries.append((st.st_mtime, st.st_size, p))
        except OSError:
            return
        entries.sort(key=lambda e: e[0], reverse=True)  # más reciente primero
        total = 0
        for i, (_, size, p) in enumerate(entries):
            total += size
            if i >= self.max_files or total > self.max_bytes:
                p.unlink(missing_ok=True)

    async def get_or_render(self, key: str, fmt: str, render: Callable[[], Awaitable[bytes]]) -> bytes:
        """Devuelve la imagen de la caché o la renderiza UNA sola vez por clave aunque
        lleguen varias peticiones a la vez: las demás esperan al lock y se llevan el mismo
        resultado (también si no hay disco)."""
        disk = self._usable()
        path = self._path(key, fmt)
        if disk:
            data = await asyncio.to_thread(self._read, path)
            if data is not None:
                return data
        lock = self._locks.setdefault(key, asyncio.Lock())
        self._waiters[key] = self._waiters.get(key, 0) + 1
        try:
            async with lock:
                data = self._inflight.get(key)
                if data is None and disk:
                    data = await asyncio.to_thread(self._read, path)
                if data is not None:
                    return data
                data = await render()
                self._inflight[key] = data
                if disk:
                    await asyncio.to_thread(self._write, path, data)
                return data
        finally:
            self._waiters[key] -= 1
            if not self._waiters[key]:
                del self._waiters[key]
                self._locks.pop(key, None)
                self._inflight.pop(key, None)
