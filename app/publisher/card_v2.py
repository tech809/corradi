"""Banner v2 de oportunidad para el canal de Telegram (lo usa `pipeline.commit`).

Diferencias con el v1 (`opportunity_card.py`, banner plano de color):
  - usa la FOTO de la oportunidad (image_url de Pexels/subida, o el pool de reserva) de fondo
  - el texto (categoría + título) va superpuesto sobre la foto, con degradado para leerse
  - formato un poco más horizontal
  - marco de color según el tipo de evento (azul YE · amarillo TC · verde ECS)

`render(opp)` es drop-in de `opportunity_card.render`: baja la foto por su cuenta y nunca
lanza (una foto rota cae al pool y luego a un degradado del color del tipo).

Previsualizar por Telegram (manda al primer ADMIN_TELEGRAM_IDS):
    docker compose run --rm --no-deps bot python -m app.publisher.card_v2 [CORRADI-2026-0123 ...]
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from app.config import cfg
from app.publisher.opportunity_card import CAT_COLORS, CAT_LABELS, _flag

log = logging.getLogger("corradi.card_v2")

_FONT_DIR = Path(__file__).resolve().parent.parent / "api" / "static" / "fonts"
_POOL_DIR = Path(__file__).resolve().parent.parent / "api" / "static" / "pool"

W, H = 1200, 350          # un poco más horizontal que el v1 (1200×360)
FRAME = 13                # grosor del marco de color por tipo
WHITE = "#ffffff"


def _font(name: str, size: int):
    from PIL import ImageFont
    p = _FONT_DIR / name
    if p.exists():
        return ImageFont.truetype(str(p), size)
    # fallback: DejaVu del contenedor
    dv = Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if "Bold" in name else "DejaVuSans.ttf")
    if dv.exists():
        return ImageFont.truetype(str(dv), size)
    return ImageFont.load_default(size=size)


def _hash_id(s: str) -> int:
    h = 0
    for ch in str(s or ""):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def pool_photo(identifier: str | None) -> bytes | None:
    files = sorted(_POOL_DIR.glob("*.jpg"))
    if not files:
        return None
    return files[_hash_id(identifier) % len(files)].read_bytes()


def _wrap(d: "ImageDraw.ImageDraw", text: str, f, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_title(d, title: str, max_w: int) -> tuple[list[str], Any]:
    one = _font("Sora-ExtraBold.ttf", 66)
    if d.textlength(title, font=one) <= max_w:
        return [title], one
    f = _font("Sora-ExtraBold.ttf", 48)
    lines = _wrap(d, title, f, max_w)
    while len(lines) > 2 and f.size > 36:
        f = _font("Sora-ExtraBold.ttf", f.size - 3)
        lines = _wrap(d, title, f, max_w)
    if len(lines) > 2:
        rest = " ".join(lines[1:])
        while d.textlength(rest + "…", font=f) > max_w and len(rest) > 1:
            rest = rest[:-1].rstrip()
        lines = [lines[0], rest + "…"]
    return lines, f


def _fetch_photo(opp: dict[str, Any]) -> bytes | None:
    """Bytes de la foto de fondo. Orden: image_url (http o /media local) → pool de reserva.
    Nunca lanza: si algo falla, devuelve None y `_render` usa el degradado del tipo."""
    url = (opp.get("image_url") or "").strip()
    try:
        if url.startswith("http"):
            import httpx
            r = httpx.get(url, timeout=15, follow_redirects=True,
                          headers={"User-Agent": "corradi-bot"})
            r.raise_for_status()
            return r.content
        if url.startswith("/media/opportunities/"):
            p = Path(cfg.media_dir) / "opportunities" / url.rsplit("/", 1)[-1]
            if p.is_file():
                return p.read_bytes()
    except Exception:  # noqa: BLE001 — una foto nunca bloquea la publicación
        log.warning("card_v2: no pude cargar %s, uso el pool", url, exc_info=True)
    return pool_photo(opp.get("identifier"))


def render(opp: dict[str, Any]) -> bytes:
    """Drop-in de `opportunity_card.render`: baja la foto y dibuja el banner."""
    return _render(opp, _fetch_photo(opp))


def _render(opp: dict[str, Any], photo_bytes: bytes | None) -> bytes:
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    color = CAT_COLORS.get(otype, CAT_COLORS["YOUTH_EXCHANGE"])

    card = Image.new("RGB", (W, H), color)              # el color asoma como marco
    inner_box = (FRAME, FRAME, W - FRAME, H - FRAME)
    iw, ih = W - 2 * FRAME, H - 2 * FRAME

    # ── Foto de fondo ──────────────────────────────────────────────────────────
    if photo_bytes:
        try:
            photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
        except Exception:
            photo = None
    else:
        photo = None
    if photo is not None:
        photo = ImageOps.fit(photo, (iw, ih), method=Image.LANCZOS, centering=(0.5, 0.4))
    else:
        # sin foto: degradado del color del tipo, para que no quede un bloque plano
        photo = Image.new("RGB", (iw, ih), color)
        top = Image.new("RGB", (iw, ih), "#0c1020")
        m = Image.new("L", (iw, ih))
        ImageDraw.Draw(m).rectangle([0, 0, iw, ih], fill=110)
        photo = Image.composite(top, photo, m)

    # La foto se ve; solo se oscurece donde va el texto.
    photo = Image.blend(photo, Image.new("RGB", photo.size, "#0a0d16"), 0.10)
    scrim = Image.new("L", (iw, ih), 0)
    sd = ImageDraw.Draw(scrim)
    band = int(ih * 0.62)                       # franja inferior para el título
    for y in range(ih):
        t = 0.0 if y < ih - band else (y - (ih - band)) / band
        val = int(18 + 224 * (t ** 1.7))        # 18 arriba (vignette suave) -> ~242 abajo
        sd.line([(0, y), (iw, y)], fill=val)
    dark = Image.new("RGB", (iw, ih), "#05070d")
    photo = Image.composite(dark, photo, scrim)

    card.paste(photo, (FRAME, FRAME))
    d = ImageDraw.Draw(card)

    # ── Bandera arriba a la derecha ───────────────────────────────────────────
    fw, fh = 96, 62
    _flag(card, W - FRAME - 34 - fw, FRAME + 26, fw, fh, opp.get("country_code"))
    d = ImageDraw.Draw(card)

    # ── Chip de categoría arriba a la izquierda ───────────────────────────────
    cat_f = _font("Sora-Bold.ttf", 25)
    label = CAT_LABELS.get(otype, str(otype)).upper()
    tw = d.textlength(label, font=cat_f)
    cx, cy = FRAME + 34, FRAME + 30
    d.rounded_rectangle([cx, cy, cx + tw + 34, cy + 44], radius=10, fill=color)
    d.text((cx + 17, cy + 8), label, font=cat_f, fill=WHITE)

    # ── Título abajo a la izquierda, con sombra ───────────────────────────────
    max_w = iw - 80
    lines, title_f = _fit_title(d, (opp.get("title") or "").strip(), max_w)
    line_h = int(title_f.size * 1.16)
    ty = H - FRAME - 34 - line_h * len(lines)
    for ln in lines:
        d.text((FRAME + 40 + 2, ty + 2), ln, font=title_f, fill=(0, 0, 0, 170))
        d.text((FRAME + 40, ty), ln, font=title_f, fill=WHITE)
        ty += line_h

    buf = io.BytesIO()
    card.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ── Driver de prueba: renderiza unas cuantas y las manda al admin por el bot ──────
if __name__ == "__main__":
    import asyncio

    from app.db import repository as repo
    from app.db.pool import close_pool, open_pool

    async def main() -> None:
        import sys

        from app.publisher import telegram_publisher as pub
        await open_pool()
        try:
            rows = await repo.list_open()
            wanted = [a for a in sys.argv[1:] if a.startswith("CORRADI-") or a[:4].isdigit()]
            wanted = {a if a.startswith("CORRADI-") else f"CORRADI-{a}" for a in wanted}
            if wanted:
                picks = [r for r in rows if r["identifier"] in wanted]
            else:
                # una de cada tipo, priorizando las que tienen foto propia y resumen
                rows.sort(key=lambda r: (not r.get("image_url"), not r.get("summary")))
                picks, seen = [], set()
                for r in rows:
                    if r.get("type") in seen:
                        continue
                    seen.add(r.get("type"))
                    picks.append(r)
                    if len(picks) >= 3:
                        break

            from telegram import Bot
            from telegram.constants import ParseMode
            bot = Bot(cfg.telegram_bot_token)
            chat_id = cfg.admin_telegram_ids[0]
            for r in picks:
                png = await asyncio.to_thread(render, r)
                # Mensaje EXACTO como saldría en el canal: imagen v2 + pie real + botones.
                caption = pub.format_opportunity(r, buttons=True, show_title=False, show_type=False)
                await bot.send_photo(
                    chat_id=chat_id, photo=png, caption=caption, parse_mode=ParseMode.HTML,
                    reply_markup=pub.opportunity_keyboard(r),
                )
                print("  enviada:", r.get("identifier"), (r.get("title") or "")[:50],
                      "| foto:", "image_url" if r.get("image_url") else "pool")
        finally:
            await close_pool()

    asyncio.run(main())
