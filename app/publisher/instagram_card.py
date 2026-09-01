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
import re
import unicodedata
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.config import cfg
from app.publisher.opportunity_card import CAT_COLORS, CAT_LABELS, WHITE, _flag, _wrap
from app.publisher.telegram_publisher import _compact_dates

FEED_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)
INK = "#101a3d"
PAPER = "#f5f2ea"
BRAND_FONT_DIR = Path(__file__).parents[1] / "api" / "static" / "fonts"

_COUNTRY_NAMES = {
    "albania": "AL", "alemania": "DE", "germany": "DE", "armenia": "AM",
    "austria": "AT", "azerbaiyan": "AZ", "belgica": "BE", "belgium": "BE",
    "bosnia y herzegovina": "BA", "bulgaria": "BG", "chipre": "CY", "cyprus": "CY",
    "croacia": "HR", "croatia": "HR", "dinamarca": "DK", "denmark": "DK",
    "eslovaquia": "SK", "slovakia": "SK", "eslovenia": "SI", "slovenia": "SI",
    "espana": "ES", "spain": "ES", "estonia": "EE", "finlandia": "FI",
    "finland": "FI", "francia": "FR", "france": "FR", "georgia": "GE",
    "grecia": "GR", "greece": "GR", "hungria": "HU", "hungary": "HU",
    "irlanda": "IE", "ireland": "IE", "islandia": "IS", "iceland": "IS",
    "italia": "IT", "italy": "IT", "letonia": "LV", "latvia": "LV",
    "liechtenstein": "LI", "lituania": "LT", "lithuania": "LT",
    "luxemburgo": "LU", "luxembourg": "LU", "malta": "MT", "marruecos": "MA",
    "moldavia": "MD", "moldova": "MD", "montenegro": "ME", "noruega": "NO",
    "norway": "NO", "paises bajos": "NL", "netherlands": "NL", "polonia": "PL",
    "poland": "PL", "portugal": "PT", "republica checa": "CZ", "czechia": "CZ",
    "rumania": "RO", "romania": "RO", "serbia": "RS", "suecia": "SE",
    "sweden": "SE", "suiza": "CH", "switzerland": "CH", "tunez": "TN",
    "turquia": "TR", "turkiye": "TR", "ucrania": "UA", "ukraine": "UA",
    "macedonia del norte": "MK", "north macedonia": "MK", "kosovo": "XK",
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Tipografía de marca incluida en el repo, idéntica en local y producción."""
    filename = "Manrope-Bold.ttf" if "Bold" in name else "Manrope-Regular.ttf"
    return ImageFont.truetype(str(BRAND_FONT_DIR / filename), size)


def _participant_country_codes(value: Any, limit: int = 9) -> tuple[list[str], int]:
    """Extrae países explícitos; omite inferencias genéricas del extractor."""
    text = str(value or "").strip()
    normal = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    vague = ("no especifica", "se asume", "se espera", "implica que", "paises del programa", "estados miembros")
    if not normal or any(phrase in normal for phrase in vague):
        return [], 0
    found: list[tuple[int, str]] = []
    for name, code in _COUNTRY_NAMES.items():
        match = re.search(rf"\b{re.escape(name)}\b", normal)
        if match:
            found.append((match.start(), code))
    codes = list(dict.fromkeys(code for _, code in sorted(found)))
    return codes[:limit], max(0, len(codes) - limit)


def _project_photo(opp: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
    """Carga la foto editorial; un fallo de red nunca bloquea la publicación."""
    url = str(opp.get("image_url") or "").strip()
    if not url:
        return None
    try:
        if url.startswith("/media/"):
            raw = (Path(cfg.media_dir) / url.removeprefix("/media/")).read_bytes()
        elif url.startswith(("https://", "http://")):
            response = httpx.get(url, timeout=12.0, follow_redirects=True)
            response.raise_for_status()
            raw = response.content
            if len(raw) > 20 * 1024 * 1024:
                return None
        else:
            return None
        with Image.open(io.BytesIO(raw)) as source:
            photo = ImageOps.exif_transpose(source).convert("RGB")
            return ImageOps.fit(photo, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.46))
    except Exception:  # noqa: BLE001
        return None


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


_ICON_DRAW = {
    "YOUTH_EXCHANGE": _compass_draw,
    "TRAINING_COURSE": _cap_draw,
    "VOLUNTEERING": _heart_draw,
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
    opp: dict[str, Any], size: tuple[int, int], pill_label: str, scale: float,
    pill_icon: str = "clock", cta_text: str = "TODA LA INFO EN EL LINK DE LA BIO",
) -> bytes:
    W, H = size
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    color = CAT_COLORS.get(otype, CAT_COLORS["YOUTH_EXCHANGE"])
    accent = _hex_to_rgb(color)

    def s(px: float) -> int:
        return round(px * scale)

    margin = s(38)
    photo = _project_photo(opp, size)
    if photo is None:
        photo = _watermark(_gradient_bg(size, color), otype, color)
    img = photo.copy()
    d = ImageDraw.Draw(img)

    # Cabecera mínima sobre la foto; una sombra discreta asegura contraste sin oscurecerla.
    brand_f = _font("DejaVuSans-Bold.ttf", s(27))
    cat_f = _font("DejaVuSans-Bold.ttf", s(22))
    d.text((margin + s(14), s(44)), "CORRADI", font=brand_f, fill="#17213e")
    d.text((margin + s(12), s(42)), "CORRADI", font=brand_f, fill=WHITE)
    category = CAT_LABELS.get(otype, otype)
    category_w = d.textlength(category, font=cat_f)
    category_x = W - margin - category_w - s(34)
    d.rounded_rectangle([category_x, s(32), W - margin, s(82)], radius=s(25), fill=accent)
    d.text((category_x + s(17), s(44)), category, font=cat_f, fill=WHITE)

    # Medimos primero el contenido: la tarjeta crece solo si título/temática lo necesitan.
    inner_x = margin + s(38)
    inner_w = W - 2 * inner_x
    edition_f = _font("DejaVuSans-Bold.ttf", s(19))
    title_f = _font("DejaVuSans-Bold.ttf", s(55))
    lines = _wrap(d, str(opp.get("title") or ""), title_f, inner_w)
    while len(lines) > 2 and title_f.size > s(40):
        title_f = _font("DejaVuSans-Bold.ttf", title_f.size - s(4))
        lines = _wrap(d, str(opp.get("title") or ""), title_f, inner_w)
    if len(lines) > 2:
        rest = " ".join(lines[1:])
        while d.textlength(rest + "…", font=title_f) > inner_w and rest:
            rest = rest[:-1].rstrip()
        lines = [lines[0], rest + "…"]
    line_h = int(title_f.size * 1.08)

    topic = re.sub(r"\s+", " ", str(opp.get("topic") or "")).strip(" .")
    topic_label_f = _font("DejaVuSans-Bold.ttf", s(19))
    topic_f = _font("DejaVuSans.ttf", s(29))
    topic_lines = _wrap(d, topic, topic_f, inner_w) if topic else []
    if len(topic_lines) > 2:
        topic_lines = topic_lines[:2]
        last = topic_lines[-1]
        while d.textlength(last + "…", font=topic_f) > inner_w and last:
            last = last[:-1].rstrip()
        topic_lines[-1] = last + "…"

    participant_codes, participant_extra = _participant_country_codes(opp.get("eligibility_countries"))
    participants_h = s(29 + 36 + 18) if participant_codes else 0

    panel_h = (
        s(34 + 37 + 19 + 32 + 28 + 58 + 44 + 28)
        + line_h * len(lines)
        + (s(32 + 36 * len(topic_lines)) if topic_lines else 0)
        + participants_h
    )
    # En story la interfaz de Instagram ocupa arriba y abajo: centramos la tarjeta en la
    # zona segura. En feed permanece anclada abajo, donde funciona como pie editorial.
    panel_y = (H - panel_h) // 2 if size == STORY_SIZE else H - margin - panel_h
    panel_bottom = panel_y + panel_h
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    shadow_box = [margin + s(3), panel_y + s(10), W - margin + s(3), panel_bottom + s(7)]
    pd.rounded_rectangle(shadow_box, radius=s(34), fill=(6, 12, 32, 55))
    panel_box = [margin, panel_y, W - margin, panel_bottom]
    pd.rounded_rectangle(panel_box, radius=s(34), fill=PAPER)
    img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
    d = ImageDraw.Draw(img)

    cursor = panel_y + s(34)
    d.text((inner_x, cursor), "NUEVA OPORTUNIDAD  ·  ERASMUS+", font=edition_f, fill=accent)
    cursor += s(37)

    for line in lines:
        d.text((inner_x, cursor), line, font=title_f, fill=INK)
        cursor += line_h
    cursor += s(19)

    if topic_lines:
        d.text((inner_x, cursor), "TEMÁTICA", font=topic_label_f, fill=accent)
        cursor += s(32)
        for line in topic_lines:
            d.text((inner_x, cursor), line, font=topic_f, fill=INK)
            cursor += s(36)

    if participant_codes:
        cursor += s(18)
        participant_label_f = _font("DejaVuSans-Bold.ttf", s(17))
        d.text((inner_x, cursor), "PAÍSES PARTICIPANTES", font=participant_label_f, fill=accent)
        cursor += s(29)
        country_x = inner_x
        country_w, country_h, country_gap = s(50), s(32), s(12)
        for code in participant_codes:
            _flag(img, country_x, cursor, country_w, country_h, code)
            country_x += country_w + country_gap
        if participant_extra:
            extra_f = _font("DejaVuSans-Bold.ttf", s(18))
            d = ImageDraw.Draw(img)
            d.text((country_x, cursor + s(6)), f"+{participant_extra}", font=extra_f, fill=INK)
        cursor += country_h

    # Destino y fechas se leen como una única línea editorial, no como tabla.
    cursor += s(32)
    d.line([inner_x, cursor, W - inner_x, cursor], fill="#d4cfc3", width=max(1, s(1)))
    meta_y = cursor + s(28)
    meta_f = _font("DejaVuSans-Bold.ttf", s(26))
    location = str(opp.get("location") or "")
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if len(parts) > 2:
        location = f"{parts[0]}, {parts[-1]}"
    dates = _compact_dates(opp)
    if dates == "fechas por confirmar":
        dates = ""
    meta = "  ·  ".join(bit for bit in (location, dates) if bit)
    flag_w, flag_h = s(48), s(32)
    flag_gap = s(16) if opp.get("country_code") else 0
    meta_w = inner_w - flag_w - flag_gap if opp.get("country_code") else inner_w
    while d.textlength(meta, font=meta_f) > meta_w and len(meta) > 1:
        meta = meta[:-2].rstrip(" ·,") + "…"
    meta_x = inner_x
    if opp.get("country_code"):
        _flag(img, inner_x, meta_y - s(1), flag_w, flag_h, opp.get("country_code"))
        d = ImageDraw.Draw(img)
        meta_x += flag_w + flag_gap
    d.text((meta_x, meta_y), meta, font=meta_f, fill=INK)

    deadline_y = meta_y + s(58)
    deadline_f = _font("DejaVuSans-Bold.ttf", s(21))
    deadline = f"SOLICITA HASTA  {pill_label.upper()}"
    deadline_w = d.textlength(deadline, font=deadline_f)
    d.rounded_rectangle(
        [inner_x, deadline_y, inner_x + deadline_w + s(34), deadline_y + s(44)],
        radius=s(22), fill=accent,
    )
    d.text((inner_x + s(17), deadline_y + s(10)), deadline, font=deadline_f, fill=WHITE)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def render_feed(opp: dict[str, Any], pill_label: str) -> bytes:
    return _compose(opp, FEED_SIZE, pill_label, scale=1.2, pill_icon="calendar")


def render_story(opp: dict[str, Any], pill_label: str) -> bytes:
    return _compose(opp, STORY_SIZE, pill_label, scale=1.56, pill_icon="clock")


def render_share(opp: dict[str, Any], pill_label: str) -> bytes:
    """Story compartible desde web/móvil, sin la referencia exclusiva a Instagram."""
    return _compose(
        opp, STORY_SIZE, pill_label, scale=1.56, pill_icon="clock",
        cta_text="DESCUBRE EL PROYECTO EN CORRADI",
    )
