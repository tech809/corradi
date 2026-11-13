"""Reels del piloto automático: animación con Pillow + música generada + ffmpeg.

- `reel_opportunity`: 10 s. Gancho palabra a palabra → cifras → de qué va → plazo y CTA.
- `reel_lastcall`: una oportunidad por segundo sobre fondo de color, con cierre.
Los textos llegan ya decididos desde `content.py` (solo datos fiables).
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from app.ig_auto import design as D
from app.ig_auto import music
from app.publisher.opportunity_card import _flag

W, H = D.STORY
FPS = 30
HOOK_END = 3.2


def _ease(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def _alpha(layer: Image.Image, a: float) -> Image.Image:
    layer.putalpha(layer.split()[3].point(lambda v: int(v * a)))
    return layer


def _ken(big: Image.Image, p: float, zoom: float = 0.12) -> Image.Image:
    bw, bh = big.size
    z = 1 + zoom * (1 - p)
    cw, ch = bw / z, bh / z
    cx, cy = bw / 2 + (p - .5) * bw * .04, bh / 2
    box = (round(cx - cw / 2), round(cy - ch / 2), round(cx + cw / 2), round(cy + ch / 2))
    return big.crop(box).resize((W, H), Image.BILINEAR).convert("RGBA")


def _word_pop(frame, t0, t, lines, font, y, color=D.WHITE, hl_words=()) -> None:
    d = ImageDraw.Draw(frame)
    hl_words = {w.strip("¿?.,¡!:").lower() for w in hl_words}
    k = 0
    for ln in lines:
        x = 64
        for word in ln.split(" "):
            p = _ease((t - t0 - k * 0.12) / 0.25)
            ww = d.textlength(word, font=font)
            if p > 0:
                dy = round(40 * (1 - p))
                layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                if word.strip("¿?.,").lower() in hl_words:
                    ld.rounded_rectangle([x - 10, y + dy + font.size * .14, x + ww + 10, y + dy + font.size * 1.12],
                                         radius=12, fill=D.CLAY)
                ld.text((x, y + dy), word, font=font, fill=color)
                frame.alpha_composite(_alpha(layer, p))
            x += ww + d.textlength(" ", font=font)
            k += 1
        y += round(font.size * 1.05)


def _progress(frame, t, total):
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle([64, 180, W - 64, 188], radius=4, fill=(255, 255, 255, 80))
    d.rounded_rectangle([64, 180, 64 + (W - 128) * min(1, t / total), 188], radius=4, fill=D.WHITE)


def _encode(frame_fn, duration: float, out: Path, style: str, seed: int, accents: tuple[float, ...]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        wav.write_bytes(music.render(style, duration, seed=seed, accents=accents))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-nostats", "-f", "rawvideo", "-pixel_format", "rgb24",
               "-video_size", f"{W}x{H}", "-framerate", str(FPS), "-i", "pipe:0", "-i", str(wav),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "21",
               "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for i in range(int(duration * FPS)):
                proc.stdin.write(frame_fn(i / FPS).convert("RGB").tobytes())
            proc.stdin.close()
            err = proc.stderr.read()
            proc.wait(timeout=180)
        except Exception:
            proc.kill()
            raise
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg falló: {err.decode(errors='replace')[-600:]}")


def reel_opportunity(photo, hook: dict[str, Any], stats: list[tuple[str, str]], about: str,
                     deadline_big: str, out: Path, style: str, seed: int) -> float:
    """Genera el MP4 y devuelve el instante (s) recomendado como portada."""
    duration = 10.0
    src = D.photo_fill(photo, (round(W * 1.15), round(H * 1.15))).convert("RGB")
    shade = D.gradient((W, H), D.SHADE, 60, 215, 0.2)
    hook_font = D.sora(124)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    while max(probe.textlength(x, font=hook_font) for x in hook["lines"]) > W - 150 and hook_font.size > 70:
        hook_font = D.sora(hook_font.size - 6)
    about_lines, about_font = D.fit(probe, about, lambda s: D.sora(s), 78, 52, W - 128, 4)

    def frame(t: float) -> Image.Image:
        f = _ken(src, t / duration)
        f.alpha_composite(shade)
        if t < HOOK_END:
            _word_pop(f, 0.0, t, hook["lines"], hook_font, 700, hl_words=hook.get("hl", ()))
            if hook.get("sub"):
                p = _ease((t - 0.9) / .4)
                if p > 0:
                    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    y = 700 + round(hook_font.size * 1.05) * len(hook["lines"]) + 30
                    ImageDraw.Draw(layer).text((66, y), hook["sub"], font=D.man(40, "SemiBold"), fill=D.SOFT)
                    f.alpha_composite(_alpha(layer, p))
        elif t < 5.6:
            d = ImageDraw.Draw(f)
            for n, (num, lab) in enumerate(stats[:3]):
                p = _ease((t - HOOK_END - n * .25) / .3)
                if p <= 0:
                    continue
                y = 600 + n * 260 + round(30 * (1 - p))
                d.text((64, y), num, font=D.sora(120 if len(num) <= 7 else 92), fill=D.WHITE)
                d.text((70, y + 150), lab, font=D.man(42, "SemiBold"), fill=D.PEACH)
        elif t < 7.6:
            p = _ease((t - 5.6) / .4)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.text((64, 600), "De qué va", font=D.man(56), fill=D.PEACH)
            y = 690
            for ln in about_lines:
                ld.text((64, y), ln, font=about_font, fill=D.WHITE)
                y += round(about_font.size * 1.15)
            f.alpha_composite(_alpha(layer, p))
        else:
            p = _ease((t - 7.6) / .4)
            panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            pd = ImageDraw.Draw(panel)
            top = 560 + round(120 * (1 - p))
            pd.rounded_rectangle([56, top, W - 56, top + 760], radius=48, fill=D.PAPER)
            pd.text((110, top + 70), "Plazo", font=D.man(56), fill=D.CLAY)
            pd.text((106, top + 140), deadline_big, font=D.sora(170), fill=D.INK)
            pd.text((110, top + 410), "Link en la bio", font=D.man(48), fill=D.INK)
            pd.text((110, top + 490), "Guárdalo y etiqueta a tu +1", font=D.man(42, "SemiBold"), fill=D.MUTED)
            D.mark(panel, W - 190, top + 630, 150, D.CLAY)
            f.alpha_composite(_alpha(panel, p))
        _progress(f, t, duration)
        return f

    _encode(frame, duration, out, style, seed, accents=(HOOK_END, 5.6, 7.6))
    return 1.6


def reel_lastcall(items: list[dict[str, Any]], out: Path, style: str, seed: int, bg: str = "clay") -> float:
    base, fg, accent = D.BACKGROUNDS[bg if bg in ("clay", "ink") else "clay"]
    items = items[:6]
    intro, per, outro = 1.6, 1.1, 1.6
    duration = intro + per * len(items) + outro

    def frame(t: float) -> Image.Image:
        f = Image.new("RGBA", (W, H), base)
        d = ImageDraw.Draw(f)
        if t < intro:
            p = _ease(t / .4)
            d.text((64, 640 + round(30 * (1 - p))), "Cierran", font=D.sora(130, "SemiBold"), fill=accent)
            _word_pop(f, 0.25, t, ["esta", "semana"], D.sora(170), 800, color=fg)
        elif t < intro + per * len(items):
            k = int((t - intro) // per)
            it = items[k]
            p = _ease(((t - intro) - k * per) / .3)
            d.text((64, 420), f"{k + 1}/{len(items)}", font=D.man(40), fill=accent)
            if D.has_flag(it.get("country_code")):
                _flag(f, 64, 560 + round(40 * (1 - p)), 180, 120, it.get("country_code"))
            d = ImageDraw.Draw(f)
            d.text((64, 720 + round(40 * (1 - p))), D.TYPE_LABEL.get(it["type"], ""), font=D.man(34), fill=accent)
            lines, tf = D.fit(d, it["title"], lambda s: D.sora(s, "Bold"), 84, 54, W - 128, 3)
            y = 790 + round(40 * (1 - p))
            for ln in lines:
                d.text((64, y), ln, font=tf, fill=fg)
                y += round(tf.size * 1.12)
            D.pill(d, 64, y + 40, f"CIERRA EL {it['closes'].upper()}", D.man(34), D.INK2 if bg == "clay" else D.CLAY,
                   D.WHITE, 34, h=84)
        else:
            p = _ease((t - (duration - outro)) / .4)
            d.text((64, 700 + round(30 * (1 - p))), "Todas en el", font=D.sora(110), fill=fg)
            d.text((64, 830 + round(30 * (1 - p))), "link de la bio", font=D.sora(110, "SemiBold"), fill=accent)
            D.lockup(f, 64, 1100, 70, fg=fg, disc=D.INK2 if bg == "clay" else D.CLAY)
        _progress(f, t, duration)
        return f

    accents = tuple(intro + per * i for i in range(len(items) + 1))
    _encode(frame, duration, out, style, seed, accents=accents)
    return 1.0
