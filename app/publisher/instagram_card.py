"""Genera las imágenes de Instagram (feed 1080×1350 + story 1080×1920) para una oportunidad
recién publicada. Reutiliza la paleta/banderas/fuentes de `opportunity_card.py` — mismo
sistema visual que ya ven el canal de Telegram y el mapa, solo cambia la composición para
formato retrato: lugar/fechas/plazo van directamente en la imagen (Instagram no permite
enlaces en el pie, así que cuanta más info quepa en la imagen, menos depende del "link en
bio"). El bloque de contenido (todo menos la bandera) se centra en el hueco vertical bajo
la bandera — con tanto alto disponible, sobre todo en la story, dejarlo anclado arriba
dejaba medio cartel de color liso vacío debajo.

El fondo combina degradado diagonal (misma familia de color de la categoría, para dar
profundidad sin romper el sistema de colores) + un icono de la categoría en marca de agua
muy sutil (compás/birrete/corazón/engranaje) — diseño validado a mano, no tocar sin volver
a revisar en las 4 categorías.
"""
from __future__ import annotations

import io
import math
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from app.publisher.opportunity_card import CAT_COLORS, CAT_LABELS, WHITE, _flag, _font, _wrap
from app.publisher.telegram_publisher import _compact_dates

FEED_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _shade(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """factor < 1 oscurece, > 1 aclara (clamp 0-255)."""
    return tuple(max(0, min(255, round(c * factor))) for c in rgb)


def _gradient_bg(size: tuple[int, int], base_hex: str) -> Image.Image:
    W, H = size
    rgb = _hex_to_rgb(base_hex)
    top = _shade(rgb, 1.18)
    bottom = _shade(rgb, 0.62)

    # Degradado diagonal vía máscara rotada (rápido, delega el trabajo pesado a PIL en C
    # en vez de recorrer píxel a píxel en Python puro).
    diag = int(math.hypot(W, H))
    mask = Image.linear_gradient("L").resize((diag, diag)).rotate(45, resample=Image.BICUBIC, expand=False)
    cx, cy = mask.width // 2, mask.height // 2
    mask = mask.crop((cx - W // 2, cy - H // 2, cx - W // 2 + W, cy - H // 2 + H))
    img = Image.composite(Image.new("RGB", (W, H), bottom), Image.new("RGB", (W, H), top), mask)

    # Manchas difuminadas translúcidas en dos esquinas — dan profundidad sin distraer del texto
    blobs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    r1 = round(W * 0.55)
    bd.ellipse([-r1 * 0.4, -r1 * 0.5, r1 * 1.2, r1 * 0.9], fill=(*_shade(rgb, 1.4), 60))
    r2 = round(W * 0.5)
    bd.ellipse([W - r2 * 0.7, H - r2 * 0.6, W + r2 * 0.5, H + r2 * 0.7], fill=(*_shade(rgb, 0.4), 70))
    blobs = blobs.filter(ImageFilter.GaussianBlur(round(W * 0.06)))
    img = Image.alpha_composite(img.convert("RGBA"), blobs).convert("RGB")
    return img


def _icon_layer(size: int, color: tuple[int, int, int], alpha: int, draw_fn) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_fn(d, size, (*color, alpha))
    return layer


def _compass_draw(d: ImageDraw.ImageDraw, size: int, rgba) -> None:
    cx, cy, r = size / 2, size / 2, size * 0.42
    w = max(2, round(size * 0.02))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rgba, width=w)
    for ang in (0, 90, 180, 270):
        rad = math.radians(ang)
        x1, y1 = cx + r * 0.86 * math.sin(rad), cy - r * 0.86 * math.cos(rad)
        x2, y2 = cx + r * 1.02 * math.sin(rad), cy - r * 1.02 * math.cos(rad)
        d.line([x1, y1, x2, y2], fill=rgba, width=w)
    n = r * 0.75
    d.polygon([(cx, cy - n), (cx + n * 0.22, cy), (cx, cy + n * 0.3)], fill=rgba)
    d.polygon([(cx, cy + n), (cx - n * 0.22, cy), (cx, cy - n * 0.3)], fill=rgba)


def _cap_draw(d: ImageDraw.ImageDraw, size: int, rgba) -> None:
    cx, cy = size / 2, size * 0.42
    bw, bh = size * 0.78, size * 0.24
    d.polygon([(cx, cy - bh), (cx + bw / 2, cy), (cx, cy + bh), (cx - bw / 2, cy)], fill=rgba)
    base_w, base_h = size * 0.34, size * 0.16
    d.rounded_rectangle(
        [cx - base_w / 2, cy + bh * 0.35, cx + base_w / 2, cy + bh * 0.35 + base_h],
        radius=base_h * 0.25, fill=rgba,
    )
    w = max(2, round(size * 0.018))
    tx = cx + bw * 0.22
    d.line([tx, cy, tx + size * 0.02, cy + size * 0.4], fill=rgba, width=w)
    d.ellipse(
        [tx + size * 0.02 - size * 0.03, cy + size * 0.4, tx + size * 0.02 + size * 0.03, cy + size * 0.4 + size * 0.06],
        fill=rgba,
    )


def _heart_draw(d: ImageDraw.ImageDraw, size: int, rgba) -> None:
    cx, cy, r = size / 2, size * 0.42, size * 0.22
    d.ellipse([cx - 2 * r * 0.95, cy - r, cx, cy + r], fill=rgba)
    d.ellipse([cx, cy - r, cx + 2 * r * 0.95, cy + r], fill=rgba)
    d.polygon(
        [(cx - 2 * r * 0.92, cy + r * 0.3), (cx + 2 * r * 0.92, cy + r * 0.3), (cx, cy + r * 2.5)],
        fill=rgba,
    )


def _gear_draw(d: ImageDraw.ImageDraw, size: int, rgba) -> None:
    cx, cy, r = size / 2, size / 2, size * 0.34
    tw, th = size * 0.1, size * 0.16
    for i in range(8):
        ang = math.radians(i * 45)
        tx, ty = cx + r * math.sin(ang), cy - r * math.cos(ang)
        pts = []
        for dx, dy in [(-tw / 2, -th / 2), (tw / 2, -th / 2), (tw / 2, th / 2), (-tw / 2, th / 2)]:
            rx = dx * math.cos(ang) - dy * math.sin(ang)
            ry = dx * math.sin(ang) + dy * math.cos(ang)
            pts.append((tx + rx, ty + ry))
        d.polygon(pts, fill=rgba)
    d.ellipse([cx - r * 0.75, cy - r * 0.75, cx + r * 0.75, cy + r * 0.75], fill=rgba)
    hole = r * 0.32
    d.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(0, 0, 0, 0))


_ICON_DRAW = {
    "YOUTH_EXCHANGE": _compass_draw,
    "TRAINING_COURSE": _cap_draw,
    "VOLUNTEERING": _heart_draw,
    "WORKSHOP": _gear_draw,
}


def _watermark(img: Image.Image, otype: str, base_hex: str) -> Image.Image:
    W, H = img.size
    size = round(W * 0.85)
    rgb = _shade(_hex_to_rgb(base_hex), 1.5)
    draw_fn = _ICON_DRAW.get(otype, _compass_draw)
    layer = _icon_layer(size, rgb, 48, draw_fn)
    layer = layer.rotate(-14, resample=Image.BICUBIC, expand=True)
    img = img.convert("RGBA")
    px = round(W * 0.10)
    py = round(H * 0.40)
    img.alpha_composite(layer, (px, py))
    return img.convert("RGB")


def _dot(d: ImageDraw.ImageDraw, x: float, y: float, r: float, color) -> None:
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def _calendar_icon(d: ImageDraw.ImageDraw, x: float, y: float, size: float, color, width: int = 3) -> None:
    d.rounded_rectangle([x, y, x + size, y + size * 0.85], radius=3, outline=color, width=width)
    d.line([x + size * 0.28, y - size * 0.14, x + size * 0.28, y + size * 0.14], fill=color, width=width)
    d.line([x + size * 0.72, y - size * 0.14, x + size * 0.72, y + size * 0.14], fill=color, width=width)
    d.line([x, y + size * 0.34, x + size, y + size * 0.34], fill=color, width=2)


def _clock_icon(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color, width: int = 4) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)
    d.line([cx, cy, cx, cy - r * 0.6], fill=color, width=width)
    d.line([cx, cy, cx + r * 0.45, cy + r * 0.15], fill=color, width=width)
    _dot(d, cx, cy, width * 0.7, color)


def _compose(
    opp: dict[str, Any], size: tuple[int, int], pill_label: str, scale: float, pill_icon: str = "clock",
) -> bytes:
    W, H = size
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    color = CAT_COLORS.get(otype, CAT_COLORS["YOUTH_EXCHANGE"])
    img = _gradient_bg(size, color)
    img = _watermark(img, otype, color)
    d = ImageDraw.Draw(img)
    x0 = round(76 * scale)
    max_w = W - x0 - round(60 * scale)

    def s(px: float) -> int:
        return round(px * scale)

    fw, fh = s(140), s(92)
    flag_bottom = s(70) + fh
    _flag(img, W - x0 - fw, s(70), fw, fh, opp.get("country_code"))
    d = ImageDraw.Draw(img)

    # ── Fase 1: medir cada bloque sin dibujar, para poder centrar el conjunto ──────────
    cat_f = _font("DejaVuSans.ttf", s(36))
    cat_h = int(cat_f.size * 1.3)

    title = opp.get("title") or ""
    title_f = _font("DejaVuSans-Bold.ttf", s(96))
    lines = _wrap(d, title, title_f, max_w)
    while len(lines) > 3 and title_f.size > s(52):
        title_f = _font("DejaVuSans-Bold.ttf", title_f.size - s(6))
        lines = _wrap(d, title, title_f, max_w)
    title_line_h = int(title_f.size * 1.2)
    title_h = title_line_h * len(lines)

    meta_f = _font("DejaVuSans.ttf", s(40))
    location = opp.get("location") or ""
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if len(parts) > 2:
        location = f"{parts[0]}, {parts[-1]}"
    dates = _compact_dates(opp)
    if dates == "fechas por confirmar":
        dates = ""
    meta_row_h = s(60)
    meta_rows = int(bool(location)) + int(bool(dates))
    meta_h = meta_row_h * meta_rows

    pill_f = _font("DejaVuSans-Bold.ttf", s(38))
    pill_h = s(76)

    cta_f = _font("DejaVuSans-Bold.ttf", s(32))
    cta = "TODA LA INFO EN EL LINK DE LA BIO"
    cta_lines = _wrap(d, cta, cta_f, max_w)
    cta_line_h = s(40)
    cta_h = cta_line_h * len(cta_lines)

    gap_cat_title, gap_title_meta, gap_meta_pill, gap_pill_cta = s(40), s(50), s(70), s(50)
    total_h = (
        cat_h + gap_cat_title + title_h + gap_title_meta + meta_h
        + (gap_meta_pill if meta_h else gap_title_meta) + pill_h + gap_pill_cta + cta_h
    )

    # ── Fase 2: dibujar, centrado en el hueco entre la bandera y el borde inferior ──────
    area_top = flag_bottom + s(20)
    area_bottom = H - s(60)
    top = area_top + max(0, (area_bottom - area_top - total_h) // 2)

    cursor = top
    d.text((x0, cursor), CAT_LABELS.get(otype, otype), font=cat_f, fill=WHITE)
    cursor += cat_h + gap_cat_title

    for ln in lines:
        d.text((x0, cursor), ln, font=title_f, fill=WHITE)
        cursor += title_line_h
    cursor += gap_title_meta

    if location:
        _dot(d, x0 + s(7), cursor + s(20), s(7), WHITE)
        d.text((x0 + s(28), cursor), location, font=meta_f, fill=WHITE)
        cursor += meta_row_h
    if dates:
        _calendar_icon(d, x0 + s(4), cursor + s(8), s(26), WHITE)
        d.text((x0 + s(42), cursor), dates, font=meta_f, fill=WHITE)
        cursor += meta_row_h
    cursor += gap_meta_pill if meta_h else 0

    pill_text = pill_label.upper()
    tw = d.textlength(pill_text, font=pill_f)
    d.rounded_rectangle([x0, cursor, x0 + tw + s(100), cursor + pill_h], radius=pill_h // 2, fill=WHITE)
    if pill_icon == "calendar":
        _calendar_icon(d, x0 + s(30), cursor + pill_h // 2 - s(12), s(26), color, width=max(2, s(3)))
    else:
        _clock_icon(d, x0 + s(40), cursor + pill_h // 2, s(20), color, width=max(2, s(4)))
    d.text((x0 + s(76), cursor + s(19)), pill_text, font=pill_f, fill=color)
    cursor += pill_h + gap_pill_cta

    for ln in cta_lines:
        d.text((x0, cursor), ln, font=cta_f, fill=WHITE)
        cursor += cta_line_h

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def render_feed(opp: dict[str, Any], pill_label: str) -> bytes:
    return _compose(opp, FEED_SIZE, pill_label, scale=1.0, pill_icon="calendar")


def render_story(opp: dict[str, Any], pill_label: str) -> bytes:
    return _compose(opp, STORY_SIZE, pill_label, scale=1.3, pill_icon="clock")
