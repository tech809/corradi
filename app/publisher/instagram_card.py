"""Genera las imágenes de Instagram (feed 1080×1350 + story 1080×1920) para una oportunidad
recién publicada. Reutiliza la paleta/banderas/fuentes de `opportunity_card.py` — mismo
sistema visual que ya ven el canal de Telegram y el mapa, solo cambia la composición para
formato retrato: lugar/fechas/plazo van directamente en la imagen (Instagram no permite
enlaces en el pie, así que cuanta más info quepa en la imagen, menos depende del "link en
bio"). El bloque de contenido (todo menos la bandera) se centra en el hueco vertical bajo
la bandera — con tanto alto disponible, sobre todo en la story, dejarlo anclado arriba
dejaba medio cartel de color liso vacío debajo.
"""
from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageDraw

from app.publisher.opportunity_card import CAT_COLORS, CAT_LABELS, WHITE, _flag, _font, _wrap
from app.publisher.telegram_publisher import _compact_dates

FEED_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)


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


def _compose(opp: dict[str, Any], size: tuple[int, int], days_left_label: str, scale: float) -> bytes:
    W, H = size
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    color = CAT_COLORS.get(otype, CAT_COLORS["YOUTH_EXCHANGE"])
    img = Image.new("RGB", (W, H), color)
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
    cta = "MÁS INFO Y FORMULARIO EN EL LINK DE LA BIO"
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

    pill_text = days_left_label.upper()
    tw = d.textlength(pill_text, font=pill_f)
    d.rounded_rectangle([x0, cursor, x0 + tw + s(100), cursor + pill_h], radius=pill_h // 2, fill=WHITE)
    _clock_icon(d, x0 + s(40), cursor + pill_h // 2, s(20), color, width=max(2, s(4)))
    d.text((x0 + s(76), cursor + s(19)), pill_text, font=pill_f, fill=color)
    cursor += pill_h + gap_pill_cta

    for ln in cta_lines:
        d.text((x0, cursor), ln, font=cta_f, fill=WHITE)
        cursor += cta_line_h

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def render_feed(opp: dict[str, Any], days_left_label: str) -> bytes:
    return _compose(opp, FEED_SIZE, days_left_label, scale=1.0)


def render_story(opp: dict[str, Any], days_left_label: str) -> bytes:
    return _compose(opp, STORY_SIZE, days_left_label, scale=1.3)
