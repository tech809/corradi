"""Genera todas las piezas de marca de Corradi (logo «Estrella polar», opción 4 elegida el
2026-11-06) a partir de una única geometría. Escribe SVG maestros en design/svg y los
exporta a PNG con Chrome sin interfaz (design/png), más favicon.ico.

    .venv/bin/python design/build.py

Si se cambia la geometría o los colores, se cambia aquí y se vuelve a ejecutar.
"""
from __future__ import annotations

import math
import pathlib
import subprocess
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent
SVG = ROOT / "svg"
PNG = ROOT / "png"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

INK, INK2, CLAY, CLAY2, PAPER, WHITE, SAGE = "#263528", "#1b281e", "#ad573e", "#89422d", "#f7f0e2", "#fffaf1", "#dce1ca"
SERIF = "Georgia, 'Times New Roman', serif"
SANS = "Manrope, 'Helvetica Neue', Arial, sans-serif"


# ---------- geometría (lienzo 200×200) ----------
def _pt(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def _arc(cx=100, cy=100, r=72, a0=42, a1=-42):
    (x0, y0), (x1, y1) = _pt(cx, cy, r, a0), _pt(cx, cy, r, a1)
    return f"M{x0:.2f} {y0:.2f}A{r} {r} 0 1 0 {x1:.2f} {y1:.2f}"


def _spark(cx=104, cy=100, big=40, small=9):
    return (f"M{cx} {cy - big}L{cx + small} {cy - small}L{cx + big} {cy}L{cx + small} {cy + small}"
            f"L{cx} {cy + big}L{cx - small} {cy + small}L{cx - big} {cy}L{cx - small} {cy - small}Z")


def mark(color: str, *, scale=1.0, tx=0.0, ty=0.0) -> str:
    """El símbolo: C abierta a la derecha + estrella polar de cuatro puntas."""
    return (f'<g transform="translate({tx} {ty}) scale({scale})">'
            f'<path d="{_arc()}" fill="none" stroke="{color}" stroke-width="24" stroke-linecap="round"/>'
            f'<path d="{_spark()}" fill="{color}"/></g>')


def svg(w, h, body, bg=None) -> str:
    rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{rect}{body}</svg>\n'


def disc(cx, cy, r, bg=CLAY, fg=WHITE, pad=0.62):
    """Disco con el símbolo dentro, con aire suficiente para que la C no toque el borde."""
    s = 2 * r * pad / 200
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{bg}"/>' + mark(fg, scale=s, tx=cx - 100 * s, ty=cy - 100 * s)


def circle_icon(size, bg, fg, pad=0.62):
    """Disco de color con el símbolo centrado (perfiles circulares)."""
    s = size * pad / 200
    return svg(size, size, f'<circle cx="{size/2}" cy="{size/2}" r="{size/2}" fill="{bg}"/>' +
               mark(fg, scale=s, tx=(size - 200 * s) / 2, ty=(size - 200 * s) / 2))


def square_icon(size, bg, fg, pad=0.6, radius=0.22):
    s = size * pad / 200
    r = size * radius
    return svg(size, size, f'<rect width="{size}" height="{size}" rx="{r}" fill="{bg}"/>' +
               mark(fg, scale=s, tx=(size - 200 * s) / 2, ty=(size - 200 * s) / 2))


def full_bleed(size, bg, fg, pad=0.5):
    """Fondo a sangre (Instagram/Telegram/WhatsApp recortan en círculo): símbolo dentro de la zona segura."""
    s = size * pad / 200
    return svg(size, size, mark(fg, scale=s, tx=(size - 200 * s) / 2, ty=(size - 200 * s) / 2), bg=bg)


def lockup(fg, sub_color, w=1040, h=260, sub=True):
    """Logo horizontal: disco arcilla + símbolo blanco + «Corradi» en serif."""
    dsc = disc(130, 130, 110)
    word = (f'<text x="280" y="{150 if sub else 168}" font-family="{SERIF}" font-size="132" letter-spacing="-4" fill="{fg}">Corradi</text>')
    tag = (f'<text x="286" y="212" font-family="{SANS}" font-weight="700" font-size="25" letter-spacing="6" fill="{sub_color}">ERASMUS+ EN CLARO</text>' if sub else "")
    return svg(w, h, dsc + word + tag)


def stacked(fg, sub_color, w=720, h=760):
    dsc = disc(360, 230, 200)
    word = f'<text x="360" y="580" text-anchor="middle" font-family="{SERIF}" font-size="150" letter-spacing="-5" fill="{fg}">Corradi</text>'
    tag = f'<text x="360" y="660" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="30" letter-spacing="8" fill="{sub_color}">ERASMUS+ EN CLARO</text>'
    return svg(w, h, dsc + word + tag)


def bot_avatar(size=640):
    """Bot de Telegram: fondo tinta, símbolo papel y una burbuja arcilla (que se note que es el bot)."""
    s = size * 0.46 / 200
    body = mark(PAPER, scale=s, tx=size * 0.2, ty=size * 0.22)
    bx, by, br = size * 0.66, size * 0.66, size * 0.14
    bubble = (f'<circle cx="{bx}" cy="{by}" r="{br}" fill="{CLAY}"/>'
              f'<path d="M{bx - br * .55} {by + br * .55}L{bx - br * 1.05} {by + br * 1.05}L{bx - br * .05} {by + br * .9}Z" fill="{CLAY}"/>'
              + "".join(f'<circle cx="{bx + dx * br * .42}" cy="{by}" r="{br * .13}" fill="{WHITE}"/>' for dx in (-1, 0, 1)))
    return svg(size, size, body + bubble, bg=INK)


def bot_banner(w=640, h=360):
    """Imagen de descripción del bot (Telegram la muestra antes de pulsar «Iniciar»)."""
    dsc = disc(150, 180, 92)
    t1 = f'<text x="276" y="160" font-family="{SERIF}" font-size="54" letter-spacing="-1.5" fill="{PAPER}">Bot de Corradi</text>'
    t2 = f'<text x="278" y="206" font-family="{SANS}" font-weight="600" font-size="21" fill="#c9c6b6">Reenvíame una convocatoria</text>'
    t3 = f'<text x="278" y="236" font-family="{SANS}" font-weight="600" font-size="21" fill="#c9c6b6">Erasmus+ y la publicamos.</text>'
    return svg(w, h, dsc + t1 + t2 + t3, bg=INK2)


def og_image(w=1200, h=630):
    deco = f'<circle cx="1040" cy="120" r="300" fill="{SAGE}" opacity=".55"/>'
    dsc = disc(168, 196, 76)
    brand = f'<text x="270" y="222" font-family="{SERIF}" font-size="76" letter-spacing="-2.5" fill="{INK}">Corradi</text>'
    h1 = (f'<text x="92" y="388" font-family="{SERIF}" font-size="70" letter-spacing="-2.5" fill="{INK}">Todos los proyectos en Europa,</text>'
          f'<text x="92" y="468" font-family="{SERIF}" font-style="italic" font-size="70" letter-spacing="-2.5" fill="{CLAY}">más accesibles.</text>')
    sub = f'<text x="94" y="548" font-family="{SANS}" font-weight="600" font-size="26" fill="#656e62">Intercambios, cursos y voluntariado europeo · mapa.proactivefuture.eu</text>'
    return svg(w, h, deco + dsc + brand + h1 + sub, bg=PAPER)


# ---------- catálogo de piezas ----------
ASSETS: dict[str, tuple[str, int, int]] = {}


def add(name, content, w, h):
    ASSETS[name] = (content, w, h)


def build_catalog():
    add("corradi-mark-ink", svg(200, 200, mark(INK)), 200, 200)
    add("corradi-mark-clay", svg(200, 200, mark(CLAY)), 200, 200)
    add("corradi-mark-white", svg(200, 200, mark(WHITE)), 200, 200)
    add("corradi-icon-circle", circle_icon(512, CLAY, WHITE), 512, 512)
    add("corradi-icon-square", square_icon(512, CLAY, WHITE), 512, 512)
    add("corradi-logo-horizontal", lockup(INK, "#656e62"), 1040, 260)
    add("corradi-logo-horizontal-white", lockup(PAPER, "#c9c6b6"), 1040, 260)
    add("corradi-logo-stacked", stacked(INK, "#656e62"), 720, 760)
    add("corradi-logo-stacked-white", stacked(PAPER, "#c9c6b6"), 720, 760)
    # Redes
    add("instagram-profile-1080", full_bleed(1080, CLAY, WHITE, pad=0.5), 1080, 1080)
    add("telegram-channel-640", full_bleed(640, CLAY, WHITE, pad=0.52), 640, 640)
    add("whatsapp-channel-640", full_bleed(640, CLAY, WHITE, pad=0.52), 640, 640)
    add("telegram-bot-640", bot_avatar(640), 640, 640)
    add("telegram-bot-description-640x360", bot_banner(), 640, 360)
    add("og-share-1200x630", og_image(), 1200, 630)
    # Web
    add("favicon", circle_icon(64, CLAY, WHITE, pad=0.62), 64, 64)
    add("apple-touch-icon-180", square_icon(180, CLAY, WHITE, pad=0.58, radius=0), 180, 180)
    add("icon-192", square_icon(192, CLAY, WHITE, pad=0.6, radius=0.22), 192, 192)
    add("icon-512", square_icon(512, CLAY, WHITE, pad=0.6, radius=0.22), 512, 512)
    add("icon-maskable-512", full_bleed(512, CLAY, WHITE, pad=0.44), 512, 512)


def render(name, content, w, h, out: pathlib.Path):
    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / "a.html"
        fonts = (ROOT.parent / "app/api/static/fonts").as_uri()
        page.write_text(
            f"<!doctype html><html><head><style>"
            f"@font-face{{font-family:Manrope;font-weight:600;src:url('{fonts}/Manrope-SemiBold.ttf')}}"
            f"@font-face{{font-family:Manrope;font-weight:700;src:url('{fonts}/Manrope-Bold.ttf')}}"
            f"html,body{{margin:0;background:transparent}}svg{{display:block}}</style></head><body>{content}</body></html>",
            encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--default-background-color=00000000", f"--window-size={w},{h}", f"--screenshot={out}",
                        "--allow-file-access-from-files", page.as_uri()], check=True, capture_output=True, timeout=60)


def main():
    SVG.mkdir(parents=True, exist_ok=True)
    PNG.mkdir(parents=True, exist_ok=True)
    build_catalog()
    for name, (content, w, h) in ASSETS.items():
        (SVG / f"{name}.svg").write_text(content, encoding="utf-8")
        render(name, content, w, h, PNG / f"{name}.png")
        print("ok", name, f"{w}x{h}")
    # PNG grandes con fondo transparente del símbolo y del logo
    for name, scale in (("corradi-mark-ink", 5), ("corradi-mark-white", 5), ("corradi-logo-horizontal", 2), ("corradi-logo-horizontal-white", 2)):
        content, w, h = ASSETS[name]
        big = content.replace(f'width="{w}" height="{h}"', f'width="{w*scale}" height="{h*scale}"', 1)
        render(name, big, w * scale, h * scale, PNG / f"{name}@{scale}x.png")
        print("ok", f"{name}@{scale}x")
    # favicon.ico multi-tamaño
    base = Image.open(PNG / "favicon.png").convert("RGBA")
    base.save(PNG / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for px in (16, 32, 48):
        base.resize((px, px), Image.LANCZOS).save(PNG / f"favicon-{px}.png")
    print("ok favicon.ico")


if __name__ == "__main__":
    main()
