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


from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
# 360 (no 300): con título a dos líneas, 300 se quedaba corto y el texto se salía del
# banner por abajo. 360 deja sitio de sobra para categoría + hasta 2 líneas de título.
W, H = 1200, 360

# Claves = valor real de `type` en BD (el mismo que usa el LLM al extraer y que consume
# mapa.html) — el tipo de voluntariado/ESC se guarda como "VOLUNTEERING", no "ESC"; con la
# clave equivocada estos tres diccionarios caían siempre al color/icono por defecto
# (YOUTH_EXCHANGE, azul) tanto en el banner de Telegram como en el post/story/reel de
# Instagram, aunque el mapa ya mostraba el verde correcto con su propio mapeo aparte.
CAT_COLORS = {"YOUTH_EXCHANGE": "#2a78d6", "TRAINING_COURSE": "#eda100", "VOLUNTEERING": "#008300"}
CAT_LABELS = {"YOUTH_EXCHANGE": "YOUTH EXCHANGE", "TRAINING_COURSE": "TRAINING COURSE", "VOLUNTEERING": "ESC"}
WHITE = "#ffffff"

FLAG_DIR = Path(__file__).resolve().parents[1] / "api" / "static" / "flags"


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
    """Banderas locales completas, sin recortar escudos ni deformar proporciones."""
    cc = (country_code or "").strip().upper()
    cc = {"UK": "GB", "EL": "GR"}.get(cc, cc)
    path = FLAG_DIR / f"{cc.lower()}.png" if len(cc) == 2 and cc.isalpha() else None
    if path and path.is_file():
        with Image.open(path) as source:
            flag = ImageOps.contain(source.convert("RGBA"), (w, h), Image.Resampling.LANCZOS)
        base.paste(flag, (x + (w - flag.width) // 2, y + (h - flag.height) // 2), flag)
        return
    # Un país desconocido se identifica por su código; nunca se inventa una bandera.
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=4, fill="white")
    font = _font("DejaVuSans-Bold.ttf", max(10, min(26, h // 2)))
    draw.text((x + w / 2, y + h / 2), cc[:2] or "??", font=font, anchor="mm", fill="#141414")


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
