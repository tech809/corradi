"""Genera el Reel de Instagram (1080×1920, ~6s) de una oportunidad: mismo fondo (degradado
+ marca de agua de categoría) y mismo contenido que `instagram_card.py`, pero animado —
zoom-out lento del fondo + aparición escalonada de cada bloque de texto (categoría, título,
meta, pill, CTA) — con el fondo musical generado por `reel_audio.py`.

Todo el "arte" (fondo, tipografía, iconos) se apoya en las piezas ya construidas y
validadas en `instagram_card.py`: aquí solo se añade la dimensión temporal encima.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.publisher.instagram_card import (
    CAT_COLORS,
    CAT_LABELS,
    WHITE,
    _calendar_icon,
    _dot,
    _flag,
    _font,
    _gradient_bg,
    _watermark,
    _wrap,
)
from app.publisher.reel_audio import synth_wav_bytes
from app.publisher.telegram_publisher import _compact_dates

log = logging.getLogger("corradi.reel")

SIZE = (1080, 1920)
FPS = 24
DURATION = 6.0
_OVERSCAN = 1.18  # cuánto más grande se renderiza el fondo, para poder hacer zoom-out


def _layer_at_alpha(layer: Image.Image, factor: float) -> Image.Image | None:
    """Copia de `layer` con el canal alfa multiplicado por `factor` (0-1). None si no hay
    nada que pintar (factor 0) — evita trabajo de sobra en los fotogramas donde un bloque
    todavía no ha empezado a aparecer."""
    if factor <= 0.001:
        return None
    if factor >= 0.999:
        return layer
    r, g, b, a = layer.split()
    a = a.point(lambda v: int(v * factor))
    return Image.merge("RGBA", (r, g, b, a))


def _ease_in(p: float) -> float:
    """0-1 con salida suave (cubic ease-out) — más agradable que lineal para fades/zoom."""
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def _build_layers(opp: dict[str, Any]) -> tuple[list[tuple[Image.Image, float]], Image.Image]:
    """Devuelve ([(layer_rgba, t_inicio_aparicion), ...], fondo_sobredimensionado).

    Mismo cálculo de posiciones que `instagram_card._compose` (medir todo primero, centrar
    el bloque conjunto en el hueco bajo la bandera) pero cada elemento se dibuja en su
    propia capa transparente en vez de sobre un único lienzo — así se puede hacer aparecer
    cada uno en un instante distinto."""
    W, H = SIZE
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    color = CAT_COLORS.get(otype, CAT_COLORS["YOUTH_EXCHANGE"])
    scale = 1.3  # misma escala que la story (mismo tamaño de lienzo)

    bg_size = (round(W * _OVERSCAN), round(H * _OVERSCAN))
    bg = _gradient_bg(bg_size, color)
    bg = _watermark(bg, otype, color)

    def s(px: float) -> int:
        return round(px * scale)

    x0 = s(76)
    max_w = W - x0 - s(60)
    meas = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(meas)

    fw, fh = s(140), s(92)
    flag_bottom = s(70) + fh

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
    pill_label = "quedan pocos días" if opp.get("application_deadline") else "inscripción abierta"

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
    area_top = flag_bottom + s(20)
    area_bottom = H - s(60)
    top = area_top + max(0, (area_bottom - area_top - total_h) // 2)
    cursor = top

    layers: list[tuple[Image.Image, float]] = []

    def new_layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
        im = Image.new("RGBA", SIZE, (0, 0, 0, 0))
        return im, ImageDraw.Draw(im)

    # Bandera: aparece la primera, casi con el fondo.
    flag_layer, _ = new_layer()
    _flag(flag_layer, W - x0 - fw, s(70), fw, fh, opp.get("country_code"))
    layers.append((flag_layer, 0.15))

    cat_layer, dd = new_layer()
    dd.text((x0, cursor), CAT_LABELS.get(otype, otype), font=cat_f, fill=WHITE)
    layers.append((cat_layer, 0.45))
    cursor += cat_h + gap_cat_title

    title_layer, dd = new_layer()
    ty = cursor
    for ln in lines:
        dd.text((x0, ty), ln, font=title_f, fill=WHITE)
        ty += title_line_h
    layers.append((title_layer, 0.75))
    cursor += title_h + gap_title_meta

    meta_layer, dd = new_layer()
    my = cursor
    if location:
        _dot(dd, x0 + s(7), my + s(20), s(7), WHITE)
        dd.text((x0 + s(28), my), location, font=meta_f, fill=WHITE)
        my += meta_row_h
    if dates:
        _calendar_icon(dd, x0 + s(4), my + s(8), s(26), WHITE)
        dd.text((x0 + s(42), my), dates, font=meta_f, fill=WHITE)
        my += meta_row_h
    layers.append((meta_layer, 1.15))
    cursor += meta_h + (gap_meta_pill if meta_h else 0)

    pill_layer, dd = new_layer()
    pill_text = pill_label.upper()
    tw = dd.textlength(pill_text, font=pill_f)
    dd.rounded_rectangle([x0, cursor, x0 + tw + s(100), cursor + pill_h], radius=pill_h // 2, fill=WHITE)
    _calendar_icon(dd, x0 + s(30), cursor + pill_h // 2 - s(12), s(26), color, width=max(2, s(3)))
    dd.text((x0 + s(76), cursor + s(19)), pill_text, font=pill_f, fill=color)
    layers.append((pill_layer, 1.55))
    cursor += pill_h + gap_pill_cta

    cta_layer, dd = new_layer()
    cy = cursor
    for ln in cta_lines:
        dd.text((x0, cy), ln, font=cta_f, fill=WHITE)
        cy += cta_line_h
    layers.append((cta_layer, 1.9))

    return layers, bg


def _bg_frame(bg: Image.Image, p: float) -> Image.Image:
    """Recorte del fondo sobredimensionado para el instante `p` (0-1 con ease-out): empieza
    con zoom (recorte pequeño, centrado con un ligerísimo desplazamiento) y termina
    mostrando la composición completa — un "zoom-out" lento que coincide con la aparición
    del contenido, así el vídeo no se queda quieto de fondo."""
    W, H = SIZE
    bw, bh = bg.size
    ep = _ease_in(p)
    # Interpola el tamaño del recorte de W×H (máx. zoom) a bw×bh (fondo completo, sin zoom).
    crop_w = W + (bw - W) * ep
    crop_h = H + (bh - H) * ep
    # Deriva ligera del centro: arranca un poco a la izquierda/arriba de al centro real.
    drift = 0.04 * (1 - ep)
    cx = bw / 2 - bw * drift
    cy = bh / 2 - bh * drift * 0.6
    left = max(0, min(bw - crop_w, cx - crop_w / 2))
    top = max(0, min(bh - crop_h, cy - crop_h / 2))
    box = (round(left), round(top), round(left + crop_w), round(top + crop_h))
    frame = bg.crop(box)
    if frame.size != SIZE:
        frame = frame.resize(SIZE, Image.LANCZOS)
    return frame.convert("RGBA")


def _render_frames(opp: dict[str, Any]):
    layers, bg = _build_layers(opp)
    n_frames = int(DURATION * FPS)
    fade = 0.28  # segundos que tarda cada bloque en aparecer del todo
    for i in range(n_frames):
        t = i / FPS
        p = t / DURATION
        frame = _bg_frame(bg, p)
        for layer, t_start in layers:
            factor = (t - t_start) / fade
            piece = _layer_at_alpha(layer, factor)
            if piece is not None:
                frame.alpha_composite(piece)
        yield frame.convert("RGB").tobytes()


def render_reel_mp4(opp: dict[str, Any], out_path: Path) -> None:
    """Genera el .mp4 (vídeo animado + audio) y lo escribe en `out_path`. Bloqueante — se
    llama siempre desde un hilo aparte (`asyncio.to_thread`), nunca en el loop de eventos:
    la codificación con ffmpeg tarda varios segundos."""
    W, H = SIZE
    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "audio.wav"
        audio_path.write_bytes(synth_wav_bytes(DURATION))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            # -loglevel error -nostats: casi nada por stderr — se lee DESPUÉS de escribir
            # todo stdin (ver más abajo), y con la verborrea normal de progreso ffmpeg
            # puede llenar el buffer del pipe de stderr y bloquearse a mitad escribiendo
            # fotogramas (deadlock clásico de subprocess con dos pipes sin drenar).
            "ffmpeg", "-y", "-loglevel", "error", "-nostats",
            "-f", "rawvideo", "-pixel_format", "rgb24",
            "-video_size", f"{W}x{H}", "-framerate", str(FPS), "-i", "pipe:0",
            "-i", str(audio_path),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(out_path),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for raw in _render_frames(opp):
                proc.stdin.write(raw)
            proc.stdin.close()
            # NO usar proc.communicate() aquí: ya hemos escrito y cerrado stdin a mano
            # (comunicación incremental por fotograma), y communicate() intenta tocar
            # stdin de nuevo internamente — revienta con "flush of closed file".
            stderr = proc.stderr.read()
            proc.wait(timeout=120)
        except Exception:
            proc.kill()
            raise
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg falló ({proc.returncode}): {stderr.decode(errors='replace')[-800:]}")
