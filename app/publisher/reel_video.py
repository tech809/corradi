"""Genera un Reel 1080×1920 a partir de la misma tarjeta editorial que la story.

El reel tiene tres actos muy cortos: un hook relacionado con el destino, la oportunidad
completa y un cierre que invita a guardar/compartir. La tarjeta sigue siendo la fuente de
verdad visual, pero el vídeo ya no es una imagen estática con un zoom casi imperceptible.
"""
from __future__ import annotations

import io
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.publisher.instagram_card import (
    CAT_LABELS,
    INK,
    PAPER,
    WHITE,
    _font,
    _wrap,
    render_story,
)
from app.publisher.reel_audio import synth_wav_bytes

log = logging.getLogger("corradi.reel")

SIZE = (1080, 1920)
FPS = 24
DURATION = 8.0
HOOK_END = 1.65
CTA_START = 5.75
COVER_TIME = 3.2  # portada: ficha completa, no hook ni CTA
_OVERSCAN = 1.085  # margen para un movimiento visible sin descubrir bordes


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


def _ease_out(p: float) -> float:
    """0-1 con salida suave (cubic ease-out)."""
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def _smoothstep(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def _hook_copy(opp: dict[str, Any]) -> str:
    """Hook corto y siempre respaldado por los datos de la oportunidad."""
    location = str(opp.get("location") or "").strip()
    parts = [part.strip() for part in location.split(",") if part.strip()]
    destination = parts[0] if parts else ""
    # Una ciudad larga genera tres líneas torpes. Si hay país y es más breve, funciona
    # mejor como hook sin inventar ni traducir ningún dato.
    if len(destination) > 20 and len(parts) > 1 and len(parts[-1]) <= 20:
        destination = parts[-1]
    if destination:
        if len(destination) > 28:
            destination = destination[:27].rstrip() + "…"
        return f"¿TE IRÍAS A {destination.upper()}?"
    return "¿BUSCAS TU PRÓXIMA AVENTURA ERASMUS+?"


def _text_layer(text: str, font_size: int, max_width: int, y: int) -> Image.Image:
    """Texto centrado y envuelto, listo para desplazar/fundirse como una sola pieza."""
    layer = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = _font("DejaVuSans-Bold.ttf", font_size)
    lines = _wrap(d, text, font, max_width)
    while len(lines) > 3 and font.size > 54:
        font = _font("DejaVuSans-Bold.ttf", font.size - 4)
        lines = _wrap(d, text, font, max_width)
    line_h = round(font.size * 1.08)
    for line in lines[:3]:
        width = d.textlength(line, font=font)
        d.text(((SIZE[0] - width) / 2, y), line, font=font, fill=WHITE)
        y += line_h
    return layer


def _build_reel_assets(opp: dict[str, Any]) -> tuple[Image.Image, Image.Image, Image.Image]:
    """Renderiza una sola vez las tres piezas reutilizadas por todos los fotogramas."""
    from app.publisher.instagram import deadline_date_label

    card = Image.open(io.BytesIO(render_story(opp, deadline_date_label(opp)))).convert("RGB")
    bg = card.resize(
        (round(SIZE[0] * _OVERSCAN), round(SIZE[1] * _OVERSCAN)),
        Image.Resampling.LANCZOS,
    )

    hook = _text_layer(_hook_copy(opp), 92, 900, 690)
    hd = ImageDraw.Draw(hook)
    otype = opp.get("type") or "YOUTH_EXCHANGE"
    category = CAT_LABELS.get(otype, otype)
    label_font = _font("DejaVuSans-Bold.ttf", 28)
    label = f"CORRADI  ·  {category}"
    label_w = hd.textlength(label, font=label_font)
    label_x = (SIZE[0] - label_w) / 2
    hd.rounded_rectangle(
        [label_x - 28, 570, label_x + label_w + 28, 630], radius=30, fill=(255, 255, 255, 42),
    )
    hd.text((label_x, 584), label, font=label_font, fill=WHITE)
    hint_font = _font("DejaVuSans.ttf", 32)
    hint = "Mira la oportunidad en 8 segundos"
    hint_w = hd.textlength(hint, font=hint_font)
    hd.text(((SIZE[0] - hint_w) / 2, 1010), hint, font=hint_font, fill=(255, 255, 255, 225))

    cta = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cta)
    panel = (64, 530, 1016, 1370)
    cd.rounded_rectangle(panel, radius=54, fill=PAPER)
    eyebrow_font = _font("DejaVuSans-Bold.ttf", 29)
    cd.text((126, 618), "NO LA PIERDAS", font=eyebrow_font, fill="#66708f")
    title_font = _font("DejaVuSans-Bold.ttf", 78)
    cy = 690
    for line in _wrap(cd, "¿CON QUIÉN TE IRÍAS?", title_font, 820):
        cd.text((126, cy), line, font=title_font, fill=INK)
        cy += 88
    cd.line((126, 935, 954, 935), fill="#d4cfc3", width=3)
    action_font = _font("DejaVuSans-Bold.ttf", 35)
    cd.text((126, 1000), "ETIQUETA A TU +1  ·  GUÁRDALO", font=action_font, fill=INK)
    info_font = _font("DejaVuSans.ttf", 34)
    cd.text((126, 1080), "Toda la info en el link de la bio", font=info_font, fill=INK)
    cd.rounded_rectangle((126, 1185, 455, 1260), radius=38, fill=INK)
    cd.text((173, 1203), "VER PROYECTO", font=eyebrow_font, fill=WHITE)
    return bg, hook, cta


def _bg_frame(bg: Image.Image, p: float) -> Image.Image:
    """Movimiento Ken Burns visible pero seguro dentro del margen sobredimensionado."""
    W, H = SIZE
    bw, bh = bg.size
    ep = _ease_out(p)
    # Sale de un zoom del 8,5% y respira ligeramente al entrar el CTA.
    breathe = 0.025 * _smoothstep((p - 0.70) / 0.30)
    crop_w = W + (bw - W) * max(0.0, ep - breathe)
    crop_h = H + (bh - H) * max(0.0, ep - breathe)
    # Paneo diagonal: suficiente para que la foto se sienta viva, sin mover la tarjeta
    # fuera de la zona segura de Reels.
    cx = bw / 2 + (ep - 0.5) * (bw - W) * 0.65
    cy = bh / 2 + (0.5 - ep) * (bh - H) * 0.38
    left = max(0, min(bw - crop_w, cx - crop_w / 2))
    top = max(0, min(bh - crop_h, cy - crop_h / 2))
    box = (round(left), round(top), round(left + crop_w), round(top + crop_h))
    frame = bg.crop(box)
    if frame.size != SIZE:
        frame = frame.resize(SIZE, Image.LANCZOS)
    return frame.convert("RGBA")


def _composite_shifted(base: Image.Image, layer: Image.Image, alpha: float, y_shift: int = 0) -> Image.Image:
    faded = _layer_at_alpha(layer, alpha)
    if faded is not None:
        base.alpha_composite(faded, (0, y_shift))
    return base


def _compose_frame(
    bg: Image.Image, hook: Image.Image, cta: Image.Image, t: float,
) -> Image.Image:
    """Compone un instante. Separarlo hace comprobables los tres actos sin generar MP4."""
    p = max(0.0, min(1.0, t / DURATION))
    frame = _bg_frame(bg, p)

    # Acto 1: la pregunta entra rápido y se retira antes de dos segundos. El velo oculta
    # suficiente información como para crear curiosidad sin perder la foto/contexto.
    # Debe estar ya visible en el primer frame: en autoplay no podemos gastar el instante
    # que decide si alguien sigue deslizando en un fundido desde la ficha normal.
    hook_in = 1.0
    hook_out = _smoothstep((t - (HOOK_END - 0.40)) / 0.40)
    hook_alpha = hook_in * (1 - hook_out)
    if hook_alpha > 0:
        veil_alpha = round(188 * hook_alpha)
        frame = Image.alpha_composite(frame, Image.new("RGBA", SIZE, (9, 19, 52, veil_alpha)))
        y_shift = round(-35 * hook_out)
        _composite_shifted(frame, hook, hook_alpha, y_shift)

    # Acto 3: cierre grande, legible y accionable. Entra desde abajo y permanece hasta el
    # final; eso también hace que el loop vuelva al hook sin un flash blanco brusco.
    cta_in = _smoothstep((t - CTA_START) / 0.48)
    if cta_in > 0:
        frame = Image.alpha_composite(
            frame, Image.new("RGBA", SIZE, (9, 19, 52, round(142 * cta_in))),
        )
        _composite_shifted(frame, cta, cta_in, round(105 * (1 - cta_in)))

    # Indicador de progreso: mantiene ritmo incluso durante los segundos de lectura y hace
    # evidente que la pieza es corta. Se coloca bajo la interfaz superior de Instagram.
    progress = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    pd = ImageDraw.Draw(progress)
    x1, x2, y = 70, SIZE[0] - 70, 164
    pd.rounded_rectangle((x1, y, x2, y + 8), radius=4, fill=(255, 255, 255, 70))
    progress_x = x1 + round((x2 - x1) * p)
    if progress_x > x1:
        pd.rounded_rectangle((x1, y, progress_x, y + 8), radius=4, fill=WHITE)
    return Image.alpha_composite(frame, progress)


def _render_frames(opp: dict[str, Any]):
    bg, hook, cta = _build_reel_assets(opp)

    n_frames = int(DURATION * FPS)
    for i in range(n_frames):
        t = i / FPS
        frame = _compose_frame(bg, hook, cta, t)
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
