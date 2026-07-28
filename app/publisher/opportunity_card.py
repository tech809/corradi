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
CAT_COLORS = {"YOUTH_EXCHANGE": "#2a78d6", "TRAINING_COURSE": "#eda100", "VOLUNTEERING": "#008300", "WORKSHOP": "#e87ba4"}
CAT_LABELS = {"YOUTH_EXCHANGE": "YOUTH EXCHANGE", "TRAINING_COURSE": "TRAINING COURSE", "VOLUNTEERING": "ECS", "WORKSHOP": "WORKSHOP"}
WHITE = "#ffffff"

# Banderas de los 27 países de la UE + un par de asociados habituales de Erasmus+
# (Turquía, Noruega), en franjas verticales simples — suficiente a este tamaño, no busca
# ser exacto a la proporción/orientación real de cada bandera. Cualquier país fuera de
# esta lista cae al genérico (recuadro blanco + código de país).
_FLAGS: dict[str, tuple[str, ...]] = {
    "IT": ("#008C45", "#ffffff", "#CD212A"),
    "ES": ("#AA151B", "#F1BF00", "#AA151B"),
    "DE": ("#000000", "#DD0000", "#FFCE00"),
    "FR": ("#0055A4", "#ffffff", "#EF4135"),
    "PT": ("#046A38", "#DA291C"),
    "RO": ("#002B7F", "#FCD116", "#CE1126"),
    "BG": ("#ffffff", "#00966E", "#D62612"),
    "GR": ("#0D5EAF", "#ffffff"),
    "PL": ("#ffffff", "#DC143C"),
    "HR": ("#FF0000", "#ffffff", "#0093DD"),
    "CZ": ("#ffffff", "#D7141A"),
    "SE": ("#006AA7", "#FECC02"),
    "TR": ("#E30A17", "#ffffff"),
    "AT": ("#ED2939", "#ffffff", "#ED2939"),
    "NL": ("#AE1C28", "#ffffff", "#21468B"),
    "BE": ("#000000", "#FAE042", "#ED2939"),
    "IE": ("#169B62", "#ffffff", "#FF883E"),
    "DK": ("#C60C30", "#ffffff"),
    "FI": ("#ffffff", "#003580"),
    "NO": ("#EF2B2D", "#ffffff", "#002868"),
    "HU": ("#CE2939", "#ffffff", "#477050"),
    "SK": ("#ffffff", "#0B4EA2", "#EE1C25"),
    "SI": ("#ffffff", "#005DA4", "#ED1C24"),
    "EE": ("#0072CE", "#000000", "#ffffff"),
    "LV": ("#9E3039", "#ffffff", "#9E3039"),
    "LT": ("#FDB913", "#006A44", "#C1272D"),
    "MT": ("#ffffff", "#CF142B"),
    "CY": ("#ffffff", "#D57800"),
    "LU": ("#ED2939", "#ffffff", "#00A1DE"),
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


def _flag(base: Image.Image, x: int, y: int, w: int, h: int, country_code: str | None) -> None:
    stripes = _FLAGS.get((country_code or "").upper())
    flag = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flag)
    if stripes:
        seg = w / len(stripes)
        for i, col in enumerate(stripes):
            fd.rectangle([i * seg, 0, (i + 1) * seg, h], fill=col)
    else:
        # Fondo opaco + texto oscuro (nunca blanco sobre blanco — con "#ffffff33" el
        # canal alfa no se aplicaba bien y el código de país quedaba invisible).
        fd.rectangle([0, 0, w, h], fill=(255, 255, 255, 255))
        cc = (country_code or "??").upper()
        f = _font("DejaVuSans-Bold.ttf", 26)
        tw = fd.textlength(cc, font=f)
        fd.text(((w - tw) / 2, (h - 30) / 2), cc, font=f, fill=(20, 20, 20, 255))
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
