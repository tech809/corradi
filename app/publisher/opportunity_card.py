"""Genera la imagen (banner) que acompaña el post de una oportunidad en el canal.

Solo Pillow, sin IA — mismo enfoque que `scripts/make_og_image.py`. La usa `pipeline.commit()`
para publicar como foto+pie (`publish_photo_to_channel`): categoría, título y bandera van
en la imagen; el resto (lugar, fechas, descripción, plazo, contacto) va en el texto/pie, para
no repetir información entre los dos.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import math

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
# 360 (no 300): con título a dos líneas, 300 se quedaba corto y el texto se salía del
# banner por abajo. 360 deja sitio de sobra para categoría + hasta 2 líneas de título.
W, H = 1200, 360

# Claves = valor real de `type` en BD (el mismo que usa el LLM al extraer y que consume
# mapa.html) — el tipo de voluntariado/ECS se guarda como "VOLUNTEERING", no "ECS"; con la
# clave equivocada estos tres diccionarios caían siempre al color/icono por defecto
# (YOUTH_EXCHANGE, azul) tanto en el banner de Telegram como en el post/story/reel de
# Instagram, aunque el mapa ya mostraba el verde correcto con su propio mapeo aparte.
CAT_COLORS = {"YOUTH_EXCHANGE": "#2a78d6", "TRAINING_COURSE": "#eda100", "VOLUNTEERING": "#008300"}
CAT_LABELS = {"YOUTH_EXCHANGE": "YOUTH EXCHANGE", "TRAINING_COURSE": "TRAINING COURSE", "VOLUNTEERING": "ECS"}
WHITE = "#ffffff"

# Banderas de los 27 países de la UE + asociados habituales de Erasmus+ (Turquía, Noruega).
# La mayoría son franjas simples — no busca ser exacto a la proporción real de cada
# bandera, pero sí a su orientación (horizontal/vertical) y colores. Las que no son
# franjas (cruz nórdica, media luna turca, cruz griega) se dibujan aparte más abajo.
# Cualquier país fuera de estas listas cae al genérico (recuadro blanco + código de país).
_FLAGS_V: dict[str, tuple[str, ...]] = {  # franjas verticales
    "IT": ("#008C45", "#ffffff", "#CD212A"),
    "FR": ("#0055A4", "#ffffff", "#EF4135"),
    "PT": ("#046A38", "#DA291C"),
    "RO": ("#002B7F", "#FCD116", "#CE1126"),
    "BE": ("#000000", "#FAE042", "#ED2939"),
    "IE": ("#169B62", "#ffffff", "#FF883E"),
    "MT": ("#ffffff", "#CF142B"),
}
_FLAGS_H: dict[str, tuple[str, ...]] = {  # franjas horizontales, de arriba a abajo
    "ES": ("#AA151B", "#F1BF00", "#AA151B"),
    "DE": ("#000000", "#DD0000", "#FFCE00"),
    "BG": ("#ffffff", "#00966E", "#D62612"),
    "PL": ("#ffffff", "#DC143C"),
    "HR": ("#FF0000", "#ffffff", "#0093DD"),
    "CZ": ("#ffffff", "#D7141A"),
    "AT": ("#ED2939", "#ffffff", "#ED2939"),
    "NL": ("#AE1C28", "#ffffff", "#21468B"),
    "HU": ("#CE2939", "#ffffff", "#477050"),
    "SK": ("#ffffff", "#0B4EA2", "#EE1C25"),
    "SI": ("#ffffff", "#005DA4", "#ED1C24"),
    "EE": ("#0072CE", "#000000", "#ffffff"),
    "LV": ("#9E3039", "#ffffff", "#9E3039"),
    "LT": ("#FDB913", "#006A44", "#C1272D"),
    "LU": ("#ED2939", "#ffffff", "#00A1DE"),
    "CY": ("#ffffff", "#D57800"),  # simplificada, sin la silueta de la isla
}
# Cruz nórdica (fondo, color de cruz[, color de cruz interior si lleva doble borde]).
_FLAGS_NORDIC: dict[str, tuple[str, ...]] = {
    "SE": ("#006AA7", "#FECC02"),
    "FI": ("#ffffff", "#003580"),
    "DK": ("#C60C30", "#ffffff"),
    "NO": ("#EF2B2D", "#ffffff", "#002868"),
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)  # fallback si el contenedor no trae DejaVu


def _wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
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


def _star_points(cx: float, cy: float, outer_r: float, inner_r: float) -> list[tuple[float, float]]:
    """10 vértices alternando radio exterior/interior -> estrella de 5 puntas, punta arriba."""
    points = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = outer_r if i % 2 == 0 else inner_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def _draw_nordic_cross(fd: ImageDraw.ImageDraw, w: int, h: int, bg: str, cross: str, cross2: str | None = None) -> None:
    """Fondo liso + cruz descentrada hacia el asta (izquierda) — Suecia, Finlandia,
    Dinamarca, Noruega comparten este patrón, nunca son franjas."""
    fd.rectangle([0, 0, w, h], fill=bg)
    bar_h = h * 0.32   # grosor de la franja horizontal
    bar_w = h * 0.32   # grosor de la franja vertical (proporcional a la altura, no al ancho)
    cx = w * 0.33
    cy = h * 0.5
    fd.rectangle([cx - bar_w / 2, 0, cx + bar_w / 2, h], fill=cross)
    fd.rectangle([0, cy - bar_h / 2, w, cy + bar_h / 2], fill=cross)
    if cross2:
        inner_w, inner_h = bar_w * 0.45, bar_h * 0.45
        fd.rectangle([cx - inner_w / 2, 0, cx + inner_w / 2, h], fill=cross2)
        fd.rectangle([0, cy - inner_h / 2, w, cy + inner_h / 2], fill=cross2)


def _draw_turkey(fd: ImageDraw.ImageDraw, w: int, h: int) -> None:
    """Rojo sólido + media luna y estrella blancas — nunca franjas rojo/blanco."""
    fd.rectangle([0, 0, w, h], fill="#E30A17")
    cy = h / 2
    outer_r = h * 0.30
    crescent_cx = w * 0.36
    fd.ellipse([crescent_cx - outer_r, cy - outer_r, crescent_cx + outer_r, cy + outer_r], fill="#ffffff")
    inner_r = h * 0.24
    inner_cx = crescent_cx + outer_r * 0.42
    fd.ellipse([inner_cx - inner_r, cy - inner_r, inner_cx + inner_r, cy + inner_r], fill="#E30A17")
    star_r = h * 0.115
    fd.polygon(_star_points(crescent_cx + outer_r * 1.55, cy, star_r, star_r * 0.4), fill="#ffffff")


def _draw_greece(fd: ImageDraw.ImageDraw, w: int, h: int) -> None:
    """Franjas azul/blanco + cantón azul con cruz blanca — nunca dos franjas planas."""
    stripes, seg = 5, h / 5
    for i in range(stripes):
        fd.rectangle([0, i * seg, w, (i + 1) * seg], fill="#0D5EAF" if i % 2 == 0 else "#ffffff")
    canton = h * (5 / 9)
    fd.rectangle([0, 0, canton, canton], fill="#0D5EAF")
    cross_w = canton * 0.2
    fd.rectangle([canton / 2 - cross_w / 2, 0, canton / 2 + cross_w / 2, canton], fill="#ffffff")
    fd.rectangle([0, canton / 2 - cross_w / 2, canton, canton / 2 + cross_w / 2], fill="#ffffff")


def _flag(base: Image.Image, x: int, y: int, w: int, h: int, country_code: str | None) -> None:
    cc = (country_code or "").upper()
    flag = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flag)
    if cc in _FLAGS_V:
        stripes = _FLAGS_V[cc]
        seg = w / len(stripes)
        for i, col in enumerate(stripes):
            fd.rectangle([i * seg, 0, (i + 1) * seg, h], fill=col)
    elif cc in _FLAGS_H:
        stripes = _FLAGS_H[cc]
        seg = h / len(stripes)
        for i, col in enumerate(stripes):
            fd.rectangle([0, i * seg, w, (i + 1) * seg], fill=col)
    elif cc in _FLAGS_NORDIC:
        _draw_nordic_cross(fd, w, h, *_FLAGS_NORDIC[cc])
    elif cc == "TR":
        _draw_turkey(fd, w, h)
    elif cc == "GR":
        _draw_greece(fd, w, h)
    else:
        # Fondo opaco + texto oscuro (nunca blanco sobre blanco — con "#ffffff33" el
        # canal alfa no se aplicaba bien y el código de país quedaba invisible).
        fd.rectangle([0, 0, w, h], fill=(255, 255, 255, 255))
        label = cc or "??"
        f = _font("DejaVuSans-Bold.ttf", 26)
        tw = fd.textlength(label, font=f)
        fd.text(((w - tw) / 2, (h - 30) / 2), label, font=f, fill=(20, 20, 20, 255))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=16, fill=255)
    base.paste(flag, (x, y), mask)


_ONE_LINE_SIZE = 100   # tamaño fijo para título de una línea — si no cabe, se pasa a dos
_TWO_LINE_SIZE = 68    # tamaño fijo para título de dos líneas
_MIN_SIZE = 42          # suelo si ni dos líneas a _TWO_LINE_SIZE bastan (título rarísimo)


def render(opp: dict[str, Any]) -> bytes:
    """Banner mínimo: categoría + título + bandera. El resto de la ficha (lugar, fechas,
    descripción, plazo, contacto) va en el PIE del mensaje, no aquí — así no se repite
    información entre la imagen y el texto.

    Bloque categoría+título centrado en vertical (margen arriba = margen abajo). El título
    tiene un tamaño FIJO de una línea (`_ONE_LINE_SIZE`); si no cabe, pasa a dos líneas a un
    tamaño fijo menor
    (`_TWO_LINE_SIZE`) en vez de ir encogiendo la fuente hasta que quepa en una — eso dejaba
    títulos largos minúsculos y con medio banner vacío debajo. El ancho del título se limita
    para que NUNCA llegue a la columna de la bandera (importante porque ahora la categoría
    va pegada a la bandera y el título empieza justo debajo, más cerca verticalmente)."""
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    color = CAT_COLORS.get(otype, CAT_COLORS["YOUTH_EXCHANGE"])
    img = Image.new("RGB", (W, H), color)
    d = ImageDraw.Draw(img)
    x0 = 72

    fw, fh = 110, 72
    flag_x = W - x0 - fw
    _flag(img, flag_x, 38, fw, fh, opp.get("country_code"))
    d = ImageDraw.Draw(img)

    # El título nunca invade la columna de la bandera, con margen de sobra — así da igual
    # que ahora esté más cerca verticalmente de la fila categoría+bandera.
    max_w = flag_x - x0 - 30
    title = opp.get("title") or ""

    title_f = _font("DejaVuSans-Bold.ttf", _ONE_LINE_SIZE)
    if d.textlength(title, font=title_f) <= max_w:
        lines = [title]
    else:
        # Dos líneas: encoger hasta que el título ENTERO quepa en 2 líneas (no solo hasta
        # que cada palabra individual quepa) — si no, un título largo perdía silenciosamente
        # el final sin ningún aviso, porque no se repite en el texto del pie.
        title_f = _font("DejaVuSans-Bold.ttf", _TWO_LINE_SIZE)
        lines = _wrap(d, title, title_f, max_w)
        while len(lines) > 2 and title_f.size > _MIN_SIZE:
            title_f = _font("DejaVuSans-Bold.ttf", title_f.size - 4)
            lines = _wrap(d, title, title_f, max_w)
        if len(lines) > 2:
            # Ni al tamaño mínimo caben todas las palabras: recorta la 2ª línea con "…"
            # en vez de desaparecer el resto del título sin ningún indicio.
            rest = " ".join(lines[1:])
            while d.textlength(rest + "…", font=title_f) > max_w and len(rest) > 1:
                rest = rest[:-1].rstrip()
            lines = [lines[0], rest + "…"]

    # El título se queda EXACTAMENTE donde estaba (mismo cálculo de siempre: margen arriba
    # = margen abajo, hueco categoría-título de 16px). Lo único que cambia es dónde se
    # dibuja la categoría: ahora centrada en vertical con la bandera, en vez de ir pegada
    # justo encima del título.
    cat_f = _font("DejaVuSans.ttf", 30)  # regular, no bold — "más fina" que el título
    gap = 16
    cat_line_h = int(cat_f.size * 1.2)
    line_h = int(title_f.size * 1.18)
    block_h = cat_line_h + gap + line_h * len(lines)
    top_margin = (H - block_h) // 2

    cat_y = 38 + (fh - cat_line_h) // 2  # centrada en la altura de la bandera (38..38+fh)
    d.text((x0, cat_y), CAT_LABELS.get(otype, otype), font=cat_f, fill=WHITE)
    ty = top_margin + cat_line_h + gap
    for ln in lines:
        d.text((x0, ty), ln, font=title_f, fill=WHITE)
        ty += line_h

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
