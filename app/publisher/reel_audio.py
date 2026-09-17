"""Genera un fondo musical corto (pad + arpegio + pulso) para los Reels de Instagram —
100% sintetizado en Python puro (stdlib `wave`+`math`, sin numpy), NADA descargado de
internet: así no hay ninguna duda de derechos de autor sobre una pista real de terceros,
publicándose además en una cuenta pública. No suena a producción profesional, pero es un
fondo amable y sin sobresaltos, coherente en todos los Reels (misma identidad sonora que
el resto del proyecto tiene visualmente).

Acorde base: Do add9 (C4-E4-G4-D5), un pad cálido y "de posibilidad/viaje" sin tensión.
Encima, un arpegio y una percusión sintética ligera marcan el pulso. Dos pequeños acentos
coinciden con la revelación de la tarjeta y la entrada del CTA.
"""
from __future__ import annotations

import math
import struct
import wave
from io import BytesIO

_SAMPLE_RATE = 44100
_CHORD_HZ = [261.63, 329.63, 392.00, 587.33]  # C4, E4, G4, D5 (Do add9)
_ARPEGGIO_HZ = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63]  # C4-E4-G4-C5-G4-E4
_BEAT = 60 / 112


def _pad_sample(t: float, duration: float) -> float:
    """Pad sostenido: las 4 notas del acorde, entrada suave (.8s) y salida suave (1.2s)."""
    fade_in, fade_out = 0.8, 1.2
    env = min(1.0, t / fade_in) * min(1.0, (duration - t) / fade_out)
    env = max(0.0, env)
    v = 0.0
    for hz in _CHORD_HZ:
        v += math.sin(2 * math.pi * hz * t)
    return (v / len(_CHORD_HZ)) * env * 0.5


def _arpeggio_sample(t: float, duration: float) -> float:
    """Notas sueltas con envolvente percusiva (ataque rápido, caída exponencial), a ritmo
    de dos notas por beat. Baja de intensidad en el cierre para dejar respirar el CTA."""
    if t > duration - 0.65:
        return 0.0
    note_dur = _BEAT / 2
    idx = int(t / note_dur) % len(_ARPEGGIO_HZ)
    local_t = t % note_dur
    hz = _ARPEGGIO_HZ[idx]
    env = math.exp(-local_t * 7.0) * (1.0 if local_t < note_dur else 0.0)
    return math.sin(2 * math.pi * hz * t) * env * 0.18


def _rhythm_sample(t: float, duration: float) -> float:
    """Kick redondo + hat tonal muy discreto; ambos sintetizados, sin samples externos."""
    if t > duration - 0.45:
        return 0.0
    beat_t = t % _BEAT
    # Barrido corto de 105 a 52 Hz para dar un golpe audible incluso en altavoz móvil.
    kick_env = math.exp(-beat_t * 18.0)
    kick_hz = 52 + 53 * math.exp(-beat_t * 25.0)
    kick = math.sin(2 * math.pi * kick_hz * beat_t) * kick_env * 0.24

    half_t = t % (_BEAT / 2)
    hat_env = math.exp(-half_t * 55.0)
    # Mezcla inarmónica determinista: sensación de hat sin usar ruido ni aleatoriedad.
    hat = (
        math.sin(2 * math.pi * 6100 * t) + math.sin(2 * math.pi * 8170 * t)
    ) * hat_env * 0.018
    return kick + hat


def _accent_sample(t: float) -> float:
    """Acentos ascendentes en los dos cambios visuales (reveal y CTA)."""
    value = 0.0
    for start, hz in ((1.42, 784.0), (5.72, 659.25)):
        local = t - start
        if 0 <= local < 0.55:
            env = math.sin(math.pi * local / 0.55) * math.exp(-local * 2.2)
            value += math.sin(2 * math.pi * (hz + 95 * local) * local) * env * 0.10
    return value


def synth_wav_bytes(duration: float) -> bytes:
    """WAV estéreo (mismo contenido en ambos canales salvo un ligero detune/retardo en el
    derecho, para dar una anchura estéreo suave tipo "chorus" barato) listo para que
    ffmpeg lo mezcle con el vídeo."""
    n = int(_SAMPLE_RATE * duration)
    detune = 0.997  # canal derecho ligerísimamente más lento -> anchura estéreo
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)  # 16 bits
        w.setframerate(_SAMPLE_RATE)
        frames = bytearray()
        for i in range(n):
            t = i / _SAMPLE_RATE
            left = (
                _pad_sample(t, duration) + _arpeggio_sample(t, duration)
                + _rhythm_sample(t, duration) + _accent_sample(t)
            )
            right_t = t * detune
            right = (
                _pad_sample(right_t, duration) + _arpeggio_sample(right_t, duration)
                + _rhythm_sample(right_t, duration) + _accent_sample(right_t)
            )
            l16 = max(-32000, min(32000, int(left * 32000)))
            r16 = max(-32000, min(32000, int(right * 32000)))
            frames += struct.pack("<hh", l16, r16)
        w.writeframes(bytes(frames))
    return buf.getvalue()
