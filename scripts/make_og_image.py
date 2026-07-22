"""Genera la imagen de previsualización (Open Graph) del mapa.

Es la tarjeta que dibujan WhatsApp, Telegram, Instagram o LinkedIn cuando alguien pega
el enlace del mapa. Sin ella sale un recuadro gris y la gente hace menos clic.

Se genera A MANO (no en cada petición) y el PNG resultante se versiona en el repo:
    python3 scripts/make_og_image.py

Solo hace falta Pillow, y solo para regenerarla. La app no la importa nunca.
Deliberadamente NO lleva el número de oportunidades: las redes cachean la
previsualización durante mucho tiempo, así que un contador saldría desactualizado.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "app" / "api" / "static" / "og.png"
W, H = 1200, 630

# Mismos colores que la web (ver <style> en mapa.html)
BG = "#f9f9f7"
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
MUTED = "#52514e"
BRAND = "#003399"
LINE = "#e1e0d9"
# Bandera de España (sin escudo): franjas 1:2:1
ROJO = "#AA151B"
AMARILLO = "#F1BF00"
# Colores por tipo, los mismos que los pines del mapa
PINS = ["#3987e5", "#d55181", "#008300", "#c98500"]

FONT_DIR = Path("/System/Library/Fonts/Supplemental")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def pin(d: ImageDraw.ImageDraw, x: int, y: int, r: int, color: str) -> None:
    """Pin de mapa: círculo + punta triangular, con borde blanco como en la web."""
    d.ellipse([x - r, y - r, x + r, y + r], fill=color, outline=SURFACE, width=max(3, r // 4))
    d.polygon([(x - r * 0.55, y + r * 0.75), (x + r * 0.55, y + r * 0.75), (x, y + r * 1.9)],
              fill=color)
    d.ellipse([x - r * 0.34, y - r * 0.34, x + r * 0.34, y + r * 0.34], fill=SURFACE)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Franja de bandera a la izquierda (vertical, 1:2:1)
    band = 54
    d.rectangle([0, 0, band, H], fill=ROJO)
    d.rectangle([0, H // 4, band, H * 3 // 4], fill=AMARILLO)

    x0 = band + 78

    # Etiqueta superior
    d.text((x0, 96), "CORRADI ERASMUS+", font=font("Arial Bold.ttf", 30), fill=BRAND)

    # Titular
    d.text((x0, 152), "Mapa de", font=font("Arial Bold.ttf", 92), fill=TEXT)
    d.text((x0, 248), "oportunidades", font=font("Arial Bold.ttf", 92), fill=TEXT)

    # Subtítulo
    d.text((x0, 372), "Intercambios juveniles, training courses,",
           font=font("Arial.ttf", 34), fill=MUTED)
    d.text((x0, 416), "voluntariado ECS y workshops por toda Europa.",
           font=font("Arial.ttf", 34), fill=MUTED)

    # Pie: para quién es
    d.line([(x0, 486), (x0 + 470, 486)], fill=LINE, width=2)
    d.text((x0, 512), "Para residentes en España  ·  inscripción abierta",
           font=font("Arial Bold.ttf", 30), fill=BRAND)

    # Pines decorativos a la derecha, en los colores reales de cada tipo
    for i, (px, py, pr) in enumerate([(905, 205, 40), (1035, 300, 32), (880, 375, 30), (1010, 460, 26)]):
        pin(d, px, py, pr, PINS[i])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"Escrita {OUT} ({OUT.stat().st_size // 1024} KB, {W}x{H})")


if __name__ == "__main__":
    main()
