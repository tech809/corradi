"""Render de landings SEO del catálogo español, aislado de FastAPI para poder probarlo."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path


COUNTRIES = {
    "espana": ("ES", "España"), "italia": ("IT", "Italia"),
    "portugal": ("PT", "Portugal"), "francia": ("FR", "Francia"),
    "alemania": ("DE", "Alemania"), "grecia": ("GR", "Grecia"),
    "polonia": ("PL", "Polonia"), "rumania": ("RO", "Rumanía"),
    "croacia": ("HR", "Croacia"), "bulgaria": ("BG", "Bulgaria"),
    "hungria": ("HU", "Hungría"), "turquia": ("TR", "Turquía"),
    "paises-bajos": ("NL", "Países Bajos"), "belgica": ("BE", "Bélgica"),
    "chequia": ("CZ", "Chequia"), "austria": ("AT", "Austria"),
    "suecia": ("SE", "Suecia"), "finlandia": ("FI", "Finlandia"),
    "dinamarca": ("DK", "Dinamarca"), "irlanda": ("IE", "Irlanda"),
    "malta": ("MT", "Malta"), "chipre": ("CY", "Chipre"),
    "serbia": ("RS", "Serbia"), "georgia": ("GE", "Georgia"),
}
TYPES = {
    "youth-exchange": ("YOUTH_EXCHANGE", "Youth Exchanges"),
    "training-course": ("TRAINING_COURSE", "Training Courses"),
    "voluntariado": ("VOLUNTEERING", "voluntariados ESC"),
}


def build(static_dir: Path, country_slug: str, type_slug: str | None = None) -> str:
    country = COUNTRIES.get(country_slug)
    type_data = TYPES.get(type_slug) if type_slug else None
    if not country or (type_slug and not type_data):
        raise KeyError("unknown landing")
    country_code, country_name = country
    type_code, type_name = type_data or (None, "oportunidades Erasmus+")
    title = f"{type_name} en {country_name} · Corradi"
    description = (
        f"Descubre {type_name} en {country_name} con convocatorias abiertas, "
        "requisitos claros y enlaces de solicitud verificados."
    )
    suffix = f"/{type_slug}" if type_slug else ""
    canonical = f"https://mapa.proactivefuture.eu/oportunidades/{country_slug}{suffix}"
    content = (static_dir / "discover.html").read_text(encoding="utf-8")
    content = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", content, count=1)
    content = re.sub(
        r'<meta name="description" content="[^"]*">',
        f'<meta name="description" content="{html.escape(description)}">', content, count=1,
    )
    content = re.sub(
        r'<link rel="canonical" href="[^"]*">',
        f'<link rel="canonical" href="{canonical}">', content, count=1,
    )
    content = re.sub(
        r'<meta property="og:title" content="[^"]*">',
        f'<meta property="og:title" content="{html.escape(title)}">', content, count=1,
    )
    content = re.sub(
        r'<meta property="og:description" content="[^"]*">',
        f'<meta property="og:description" content="{html.escape(description)}">', content, count=1,
    )
    content = re.sub(
        r'<meta property="og:url" content="[^"]*">',
        f'<meta property="og:url" content="{canonical}">', content, count=1,
    )
    data = json.dumps(
        {"country": country_code, "countryName": country_name, "type": type_code},
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return content.replace("</head>", f"<script>window.CORRADI_LANDING={data}</script>\n</head>", 1)
