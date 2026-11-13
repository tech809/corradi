"""Piezas visuales del piloto automático de Instagram (Pillow, fuentes del repo).

Estilo «gancho» sobre la paleta Atlas: titulares enormes en Sora ExtraBold, palabra clave
sobre un marcador arcilla, foto a sangre y colores por tipo iguales que el mapa
(YE ocre · TC petróleo · ESC oliva). Solo fuentes incluidas en el repo (Sora, Manrope).

Todo lo que se escribe en las imágenes sale de `content.py`, que solo usa datos fiables
de la ficha. Aquí no se decide ningún texto, solo cómo se pinta.
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.publisher.opportunity_card import _flag

FONTS = Path(__file__).resolve().parents[1] / "api" / "static" / "fonts"
FEED = (1080, 1350)
STORY = (1080, 1920)

INK, INK2, CLAY = "#263528", "#1b281e", "#ad573e"
PAPER, WHITE, SAGE, MUTED, RULE = "#f7f0e2", "#fffaf1", "#dce1ca", "#656e62", "#d3c9b8"
PEACH, SOFT = "#e7bb9d", "#e9e4d6"
SHADE = (20, 30, 22)
TYPE_COLOR = {"YOUTH_EXCHANGE": "#c0892b", "TRAINING_COURSE": "#2f5d62", "VOLUNTEERING": "#6b8a4e"}
TYPE_LABEL = {"YOUTH_EXCHANGE": "YOUTH EXCHANGE", "TRAINING_COURSE": "TRAINING COURSE",
              "VOLUNTEERING": "VOLUNTARIADO ESC"}
BACKGROUNDS = {"clay": (CLAY, WHITE, PEACH), "ink": (INK2, WHITE, PEACH), "sage": (SAGE, INK, CLAY),
               "paper": (PAPER, INK, CLAY)}


# ───────────────────────────────── utilidades ─────────────────────────────────

def sora(size: int, weight: str = "ExtraBold") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Sora-{weight}.ttf"), size)


def man(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Manrope-{weight}.ttf"), size)


def wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: float) -> list[str]:
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(d, text, family: Callable, size: int, min_size: int, max_w: float, max_lines: int):
    """Mayor tamaño con el que `text` cabe en `max_lines` líneas; si no, recorta con «…»."""
    while True:
        f = family(size)
        lines = wrap(d, text, f, max_w)
        if len(lines) <= max_lines or size <= min_size:
            break
        size -= 4
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while d.textlength(last + "…", font=f) > max_w and " " in last:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last + "…"
    return lines, f


def tracked(d, xy, text, font, fill, track=0.12) -> float:
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + font.size * track
    return x


def tracked_w(d, text, font, track=0.12) -> float:
    return sum(d.textlength(ch, font=font) + font.size * track for ch in text) - font.size * track


def pill(d, x, y, text, font, bg, fg, pad=22, h=None, track=0.1, outline=None) -> float:
    tw = tracked_w(d, text, font, track)
    h = h or round(font.size * 2.1)
    d.rounded_rectangle([x, y, x + tw + 2 * pad, y + h], radius=h / 2, fill=bg, outline=outline,
                        width=3 if outline else 0)
    tracked(d, (x + pad, y + (h - font.size) / 2 - font.size * 0.14), text, font, fg, track)
    return x + tw + 2 * pad


def gradient(size, color, top_alpha, bottom_alpha, start=0.0) -> Image.Image:
    w, h = size
    col = Image.new("L", (1, h))
    for y in range(h):
        r = y / h
        t = max(0.0, (r - start) / (1 - start)) if r > start else 0.0
        col.putpixel((0, y), round(top_alpha + (bottom_alpha - top_alpha) * (t ** 1.4)))
    layer = Image.new("RGBA", size, color)
    layer.putalpha(col.resize(size))
    return layer


def mark(img: Image.Image, cx: float, cy: float, size: float, color: str) -> None:
    """Símbolo «Estrella polar» (misma geometría que design/build.py)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    k = size / 200
    r, w = 72 * k, 24 * k
    d.arc([cx - r, cy - r, cx + r, cy + r], start=42, end=318, fill=color, width=round(w))
    for ang in (42, -42):
        a = math.radians(ang)
        ex, ey = cx + (r - w / 2) * math.cos(a), cy - (r - w / 2) * math.sin(a)
        d.ellipse([ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2], fill=color)
    sx, big, small = cx + 4 * k, 40 * k, 9 * k
    d.polygon([(sx, cy - big), (sx + small, cy - small), (sx + big, cy), (sx + small, cy + small),
               (sx, cy + big), (sx - small, cy + small), (sx - big, cy), (sx - small, cy - small)], fill=color)
    img.alpha_composite(layer)


def lockup(img: Image.Image, x: int, y: int, h: int, fg: str = WHITE, disc: str = CLAY) -> None:
    d = ImageDraw.Draw(img)
    d.ellipse([x, y, x + h, y + h], fill=disc)
    mark(img, x + h / 2, y + h / 2, h * 0.62, WHITE)
    d = ImageDraw.Draw(img)
    d.text((x + h * 1.25, y + h * 0.52), "Corradi", font=sora(round(h * 0.62), "Bold"), fill=fg, anchor="lm")


def marker_lines(img, x, y, lines, font, fg, hl=CLAY, hl_words=(), gap=1.04, pad=14) -> int:
    """Titular grande; las palabras de `hl_words` van sobre un marcador de color."""
    d = ImageDraw.Draw(img)
    hl_words = {w.strip(".,¿?¡!:").lower() for w in hl_words}
    for ln in lines:
        cx = x
        for word in ln.split(" "):
            ww = d.textlength(word, font=font)
            if word.strip(".,¿?¡!:").lower() in hl_words:
                d.rounded_rectangle([cx - pad * .6, y + font.size * .14, cx + ww + pad * .6, y + font.size * 1.12],
                                    radius=10, fill=hl)
            d.text((cx, y), word, font=font, fill=fg)
            cx += ww + d.textlength(" ", font=font)
        y += round(font.size * gap)
    return y


def has_flag(code: str | None) -> bool:
    from app.publisher.opportunity_card import FLAG_DIR
    cc = {"UK": "GB", "EL": "GR"}.get((code or "").upper(), (code or "").upper())
    return len(cc) == 2 and (FLAG_DIR / f"{cc.lower()}.png").is_file()


def flags(img, x, y, codes, w, h, gap) -> None:
    """Fila de banderas; los países sin bandera se omiten (no se pinta el código suelto)."""
    for c in codes:
        if has_flag(c):
            _flag(img, x, y, w, h, c)
            x += w + gap


def to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92, optimize=True, progressive=True)
    return buf.getvalue()


def photo_fill(photo: Image.Image | None, size, fallback=INK2) -> Image.Image:
    if photo is None:
        return Image.new("RGBA", size, fallback)
    return ImageOps.fit(photo.convert("RGB"), size, Image.LANCZOS, centering=(0.5, 0.45)).convert("RGBA")


def _top(img, label=None, color=None, dark=True, page=None, size=FEED, y=54):
    lockup(img, 60, y, 50, fg=WHITE if dark else INK)
    d = ImageDraw.Draw(img)
    if label:
        f = man(20)
        tw = tracked_w(d, label, f, 0.12)
        pill(d, size[0] - 60 - tw - 44, y + 4, label, f, color, WHITE, 22, h=44, track=0.12)
    if page:
        d.text((size[0] - 60, size[1] - 60), page, font=man(22, "SemiBold"), fill=WHITE if dark else MUTED, anchor="rs")


def _swipe(img, dark=True, size=FEED, text="Desliza"):
    ImageDraw.Draw(img).text((60, size[1] - 60), f"{text}  →", font=man(24), fill=WHITE if dark else INK, anchor="ls")


# ───────────────────────────── carrusel de oportunidad ─────────────────────────────

def cover(photo, hook: dict[str, Any], otype: str) -> bytes:
    """Portada: foto a sangre + gancho enorme. `hook` = {lines, hl, sub}."""
    img = photo_fill(photo, FEED)
    img.alpha_composite(gradient(FEED, SHADE, 0, 205, 0.22))
    img.alpha_composite(gradient((FEED[0], 260), SHADE, 0, 120, 0.0).transpose(Image.FLIP_TOP_BOTTOM), (0, 0))
    _top(img, TYPE_LABEL.get(otype), TYPE_COLOR.get(otype, CLAY))
    d = ImageDraw.Draw(img)
    size = 118 if max(len(x) for x in hook["lines"]) <= 13 else 100
    f = sora(size)
    while max(d.textlength(x, font=f) for x in hook["lines"]) > FEED[0] - 150 and size > 70:
        size -= 6
        f = sora(size)
    y = FEED[1] - 175 - round(f.size * 1.04) * len(hook["lines"])
    y = marker_lines(img, 62, y, hook["lines"], f, WHITE, hl_words=hook.get("hl", ()))
    if hook.get("sub"):
        ImageDraw.Draw(img).text((64, y + 18), hook["sub"], font=man(30, "SemiBold"), fill=SOFT)
    _swipe(img)
    return to_jpeg(img)


def details(opp: dict[str, Any], stats: list[tuple[str, str]], summary: str) -> bytes:
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    color = TYPE_COLOR.get(otype, CLAY)
    img = Image.new("RGBA", FEED, PAPER)
    _top(img, TYPE_LABEL.get(otype), color, dark=False, page="2/3")
    d = ImageDraw.Draw(img)
    d.text((62, 180), "De qué va", font=man(34), fill=CLAY)
    lines, tf = fit(d, opp.get("title") or "", lambda s: sora(s, "Bold"), 62, 40, FEED[0] - 124, 3)
    y = 240
    for ln in lines:
        d.text((62, y), ln, font=tf, fill=INK)
        y += round(tf.size * 1.14)
    y += 18
    body = man(31, "Medium")
    lines = wrap(d, summary, body, FEED[0] - 124)
    if len(lines) > 5:
        lines = lines[:5]
        last = lines[-1]
        while d.textlength(last + "…", font=body) > FEED[0] - 124 and " " in last:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last.rstrip(" ,.;:") + "…"
    for ln in lines:
        d.text((62, y), ln, font=body, fill="#3d4a3f")
        y += 45
    y = max(y + 36, 760)
    stats = stats[:3]
    if stats:
        gap = 22
        cw = (FEED[0] - 124 - gap * (len(stats) - 1)) / len(stats)
        for n, (num, lab) in enumerate(stats):
            bx = 62 + n * (cw + gap)
            d.rounded_rectangle([bx, y, bx + cw, y + 220], radius=26, fill=WHITE, outline=RULE, width=2)
            nf = sora(80 if len(num) <= 4 else 56 if len(num) <= 7 else 44)
            d.text((bx + cw / 2, y + 96), num, font=nf, fill=color, anchor="mm")
            d.text((bx + cw / 2, y + 172), lab, font=man(27, "SemiBold"), fill=MUTED, anchor="mm")
    if has_flag(opp.get("country_code")):
        _flag(img, FEED[0] - 62 - 66, 178, 66, 44, opp["country_code"])
    return to_jpeg(img)


def apply_slide(deadline_big: str, steps: list[str], closing: str) -> bytes:
    img = Image.new("RGBA", FEED, INK2)
    _top(img, page="3/3")
    d = ImageDraw.Draw(img)
    d.text((62, 196), "Plazo", font=man(40), fill=PEACH)
    f = sora(190)
    while d.textlength(deadline_big, font=f) > FEED[0] - 124:
        f = sora(f.size - 10)
    d.text((58, 250), deadline_big, font=f, fill=WHITE)
    y = 540
    for n, st in enumerate(steps, 1):
        d.ellipse([62, y, 142, y + 80], fill=CLAY)
        d.text((102, y + 40), str(n), font=sora(40), fill=WHITE, anchor="mm")
        lines = wrap(d, st, man(34, "SemiBold"), FEED[0] - 240)[:2]
        ly = y + 40 - (len(lines) - 1) * 22
        for ln in lines:
            d.text((172, ly), ln, font=man(34, "SemiBold"), fill=PAPER, anchor="lm")
            ly += 44
        y += 122
    y += 40
    d.line([62, y, FEED[0] - 62, y], fill="#3a4a3d", width=2)
    d.text((62, y + 50), closing, font=man(36), fill=WHITE)
    return to_jpeg(img)


# ───────────────────────────── story de oportunidad ─────────────────────────────

def story(photo, hook: dict[str, Any], otype: str, deadline_pill: str) -> bytes:
    img = photo_fill(photo, STORY)
    img.alpha_composite(gradient(STORY, SHADE, 40, 225, 0.25))
    lockup(img, 64, 230, 54)
    d = ImageDraw.Draw(img)
    f = sora(124)
    while max(d.textlength(x, font=f) for x in hook["lines"]) > STORY[0] - 150 and f.size > 70:
        f = sora(f.size - 6)
    y = 1180 - round(f.size * 1.04) * len(hook["lines"])
    y = marker_lines(img, 64, y, hook["lines"], f, WHITE, hl_words=hook.get("hl", ()))
    d = ImageDraw.Draw(img)
    if hook.get("sub"):
        d.text((66, y + 24), hook["sub"], font=man(40, "SemiBold"), fill=SOFT)
        y += 70
    pill(d, 66, y + 50, deadline_pill, man(30), TYPE_COLOR.get(otype, CLAY), WHITE, 30, h=72)
    d.text((STORY[0] / 2, 1640), "Toda la info en el link de la bio", font=man(36, "SemiBold"), fill=WHITE, anchor="mm")
    return to_jpeg(img)


# ───────────────────────────── última llamada ─────────────────────────────

def lastcall_cover(count: int, flag_codes: list[str], bg: str = "clay") -> bytes:
    base, fg, accent = BACKGROUNDS[bg]
    img = Image.new("RGBA", FEED, base)
    lockup(img, 60, 54, 50, fg=fg, disc=INK2 if bg == "clay" else CLAY)
    d = ImageDraw.Draw(img)
    d.text((62, 470), "Última", font=sora(120, "SemiBold"), fill=accent)
    y = marker_lines(img, 58, 610, ["llamada"], sora(160), fg, hl=None)
    d.text((64, y + 16), f"{count} Erasmus+ que cierran esta semana", font=man(38), fill=fg)
    flags(img, 64, y + 110, list(dict.fromkeys(flag_codes))[:7], 96, 64, 20)
    _swipe(img, dark=bg in ("clay", "ink"))
    return to_jpeg(img)


def lastcall_list(items: list[dict[str, Any]], page: str) -> bytes:
    """Hasta 5 por diapositiva: bandera, tipo, título y fecha de cierre."""
    img = Image.new("RGBA", FEED, PAPER)
    _top(img, dark=False, page=page)
    d = ImageDraw.Draw(img)
    y = 180
    for it in items[:5]:
        color = TYPE_COLOR.get(it["type"], CLAY)
        d.rounded_rectangle([62, y, FEED[0] - 62, y + 200], radius=26, fill=WHITE, outline=RULE, width=2)
        if has_flag(it.get("country_code")):
            _flag(img, 92, y + 30, 66, 44, it.get("country_code"))
        d = ImageDraw.Draw(img)
        d.text((178, y + 52), TYPE_LABEL.get(it["type"], ""), font=man(20), fill=color, anchor="lm")
        lines, tf = fit(d, it["title"], lambda s: sora(s, "SemiBold"), 34, 26, FEED[0] - 62 - 92 - 210, 2)
        ty = y + 92
        for ln in lines:
            d.text((92, ty), ln, font=tf, fill=INK)
            ty += round(tf.size * 1.2)
        d.text((FEED[0] - 92, y + 52), it["closes"], font=sora(34), fill=CLAY, anchor="rm")
        y += 220
    return to_jpeg(img)


# ───────────────────────────── guías ─────────────────────────────

def guide_cover(kicker: str, lines: list[str], hl: list[str], sub: str, bg: str = "sage") -> bytes:
    base, fg, accent = BACKGROUNDS[bg]
    img = Image.new("RGBA", FEED, base)
    lockup(img, 60, 54, 50, fg=fg, disc=INK2 if bg == "clay" else CLAY)
    d = ImageDraw.Draw(img)
    d.text((62, 380), kicker, font=man(46), fill=accent)
    f = sora(136)
    while max(d.textlength(x, font=f) for x in lines) > FEED[0] - 140:
        f = sora(f.size - 6)
    y = marker_lines(img, 58, 460, lines, f, fg if bg != "clay" else WHITE, hl=CLAY if bg != "clay" else INK2,
                     hl_words=hl)
    d = ImageDraw.Draw(img)
    for ln in wrap(d, sub, man(36, "SemiBold"), FEED[0] - 124)[:2]:
        d.text((62, y + 24), ln, font=man(36, "SemiBold"), fill=fg)
        y += 48
    _swipe(img, dark=bg in ("clay", "ink"))
    return to_jpeg(img)


def guide_cards(heading: str, cards: list[tuple[str, str]], footnote: str, page: str) -> bytes:
    img = Image.new("RGBA", FEED, PAPER)
    _top(img, dark=False, page=page)
    d = ImageDraw.Draw(img)
    d.text((62, 180), heading, font=man(32), fill=CLAY)
    y = 250
    card_h = 230 if len(cards) <= 3 else 205
    for title, sub in cards[:4]:
        d.rounded_rectangle([62, y, FEED[0] - 62, y + card_h], radius=28, fill=WHITE, outline=RULE, width=2)
        d.text((104, y + 40), title, font=sora(46, "Bold"), fill=INK)
        sf = man(29, "Medium")
        for n, ln in enumerate(wrap(d, sub, sf, FEED[0] - 210)[:2]):
            d.text((104, y + 112 + n * 42), ln, font=sf, fill="#3d4a3f")
        y += card_h + 26
    if footnote:
        d.text((62, y + 14), footnote, font=man(26, "SemiBold"), fill=MUTED)
    return to_jpeg(img)


def guide_closing(kicker: str, lines: list[str], hl: list[str], sub: str, cta: str, page: str) -> bytes:
    img = Image.new("RGBA", FEED, INK2)
    _top(img, page=page)
    d = ImageDraw.Draw(img)
    d.text((62, 200), kicker, font=man(32), fill=PEACH)
    f = sora(96)
    while max(d.textlength(x, font=f) for x in lines) > FEED[0] - 140:
        f = sora(f.size - 6)
    y = marker_lines(img, 58, 262, lines, f, WHITE, hl_words=hl)
    d = ImageDraw.Draw(img)
    for ln in wrap(d, sub, man(33, "SemiBold"), FEED[0] - 124)[:2]:
        d.text((62, y + 36), ln, font=man(33, "SemiBold"), fill="#c9c6b6")
        y += 46
    d.line([62, y + 120, FEED[0] - 62, y + 120], fill="#3a4a3d", width=2)
    d.text((62, y + 170), cta, font=man(36), fill=PEACH)
    return to_jpeg(img)
