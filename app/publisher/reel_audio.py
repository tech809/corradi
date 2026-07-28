"""Genera un fondo musical corto (pad + arpegio) para los Reels de Instagram —
100% sintetizado en Python puro (stdlib `wave`+`math`, sin numpy), NADA descargado de
internet: así no hay ninguna duda de derechos de autor sobre una pista real de terceros,
publicándose además en una cuenta pública. No suena a producción profesional, pero es un
fondo amable y sin sobresaltos, coherente en todos los Reels (misma identidad sonora que
el resto del proyecto tiene visualmente).

Acorde base: Do add9 (C4-E4-G4-D5), un pad cálido y "de posibilidad/viaje" sin tensión.
Encima, un arpegio suave sobre las mismas notas marca el pulso, para que el fondo no se
quede plano y acompañe el movimiento del vídeo.
"""
from __future__ import annotations

import math
import struct
import wave
from io import BytesIO

_SAMPLE_RATE = 44100
_CHORD_HZ = [261.63, 329.63, 392.00, 587.33]  # C4, E4, G4, D5 (Do add9)
_ARPEGGIO_HZ = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63]  # C4-E4-G4-C5-G4-E4


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
    de 2.5 notas/seg — el "pulso" del fondo. Se calla en el último segundo, dejando solo
    el pad para un cierre limpio."""
    if t > duration - 1.0:
        return 0.0
    note_dur = 0.4
    idx = int(t / note_dur) % len(_ARPEGGIO_HZ)
    local_t = t % note_dur
    hz = _ARPEGGIO_HZ[idx]
    env = math.exp(-local_t * 7.0) * (1.0 if local_t < note_dur else 0.0)
    return math.sin(2 * math.pi * hz * t) * env * 0.22


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
            left = _pad_sample(t, duration) + _arpeggio_sample(t, duration)
            right = _pad_sample(t * detune, duration) + _arpeggio_sample(t * detune, duration)
            l16 = max(-32000, min(32000, int(left * 32000)))
            r16 = max(-32000, min(32000, int(right * 32000)))
            frames += struct.pack("<hh", l16, r16)
        w.writeframes(bytes(frames))
    return buf.getvalue()
