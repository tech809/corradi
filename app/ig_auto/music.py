"""Música original para los Reels, generada por código (numpy), sin descargar nada.

Así no hay dudas de derechos de autor en una cuenta pública, y cada Reel suena distinto:
hay varios estilos con su tempo, batería, bajo y acordes propios, y cada pista usa una
tonalidad, progresión y melodía elegidas por una semilla. El piloto automático guarda el
estilo como variable de experimento y aprende cuál funciona mejor.

    wav = render("house", seconds=10, seed=42)   # bytes WAV estéreo 44,1 kHz
"""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np

SR = 44100

# Escalas (semitonos desde la tónica)
MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
DORIAN = [0, 2, 3, 5, 7, 9, 10]

# Progresiones en grados de la escala (0 = I)
PROGRESSIONS = {
    "minor": [[0, 5, 2, 6], [0, 3, 4, 0], [5, 6, 0, 0], [0, 6, 5, 4]],
    "major": [[0, 4, 5, 3], [0, 5, 3, 4], [3, 4, 0, 5], [0, 3, 0, 4]],
}


@dataclass(frozen=True)
class Style:
    name: str
    bpm: tuple[int, int]
    scale: list[int]
    mode: str
    swing: float          # 0 = recto; 0,2 = algo de swing en las semicorcheas
    kick: str             # patrón de 16 pasos: x = golpe
    snare: str
    hat: str
    bass: str             # x = nota de bajo (raíz), o = quinta
    chord_rhythm: str     # x = acorde
    lead: float           # probabilidad de nota de melodía por paso de corchea
    timbre: str           # "pluck" | "keys" | "saw" | "marimba"
    brightness: float     # 0-1, cuántos armónicos
    vinyl: bool = False


STYLES: dict[str, Style] = {
    "house": Style("house", (120, 124), MINOR, "minor", 0.0,
                   kick="x...x...x...x...", snare="....x.......x...", hat="..x...x...x...x.",
                   bass="..x...x...x..xx.", chord_rhythm="x..x..x...x..x..", lead=0.25,
                   timbre="pluck", brightness=0.7),
    "lofi": Style("lofi", (78, 86), DORIAN, "minor", 0.22,
                  kick="x.....x...x.....", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                  bass="x.....x...x.....", chord_rhythm="x.......x.......", lead=0.18,
                  timbre="keys", brightness=0.35, vinyl=True),
    "afro": Style("afro", (104, 110), MAJOR, "major", 0.08,
                  kick="x..x..x...x..x..", snare="...x.......x..x.", hat="xxxxxxxxxxxxxxxx",
                  bass="x..x..x...x.....", chord_rhythm="..x...x...x...x.", lead=0.35,
                  timbre="marimba", brightness=0.55),
    "dembow": Style("dembow", (92, 98), MINOR, "minor", 0.0,
                    kick="x...x...x...x...", snare="...x..x....x..x.", hat="..x...x...x...x.",
                    bass="x..x...x..x.....", chord_rhythm="x.......x.......", lead=0.22,
                    timbre="pluck", brightness=0.5),
    "synthpop": Style("synthpop", (108, 114), MAJOR, "major", 0.0,
                      kick="x...x...x...x...", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                      bass="x.x.x.x.x.x.x.x.", chord_rhythm="x...x...x...x...", lead=0.3,
                      timbre="saw", brightness=0.8),
    "indie": Style("indie", (126, 132), MAJOR, "major", 0.0,
                   kick="x.....x.x.......", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                   bass="x...x...x...x...", chord_rhythm="x.x.x.x.x.x.x.x.", lead=0.2,
                   timbre="keys", brightness=0.6),
}


def _midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def _tone(hz: float, n: int, timbre: str, brightness: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n) / SR
    detune = 1 + rng.uniform(-0.002, 0.002)
    if timbre == "saw":
        harm = range(1, 2 + int(9 * brightness))
        w = sum(np.sin(2 * np.pi * hz * k * detune * t) / k for k in harm)
        w += sum(np.sin(2 * np.pi * hz * k * 1.006 * t) / k for k in harm) * 0.6   # coro
        return w * 0.45
    if timbre == "marimba":
        return np.sin(2 * np.pi * hz * t) + 0.35 * np.sin(2 * np.pi * hz * 4 * t) * np.exp(-t * 18)
    if timbre == "keys":   # tipo piano eléctrico: fundamental + armónicos con trémolo
        trem = 1 + 0.12 * np.sin(2 * np.pi * 5.2 * t)
        w = np.sin(2 * np.pi * hz * t) + brightness * 0.5 * np.sin(2 * np.pi * hz * 2 * t) * np.exp(-t * 3)
        return w * trem
    # pluck: armónicos que se apagan antes que la fundamental
    w = np.zeros(n)
    for k in range(1, 2 + int(7 * brightness)):
        w += np.sin(2 * np.pi * hz * k * detune * t) * np.exp(-t * (2 + 6 * k)) / k
    return w


def _kick(n: int) -> np.ndarray:
    t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t * 28)
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase) * np.exp(-t * 9) * 1.1


def _snare(n: int, rng, clap=False) -> np.ndarray:
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n + 1))        # ruido algo agudo
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)
    if clap:   # tres impactos muy juntos
        env = sum(np.exp(-np.clip(t - d, 0, None) * 45) * (t >= d) for d in (0, 0.011, 0.023))
        return noise * env * 0.15
    return noise * np.exp(-t * 22) * 0.17 + body * 0.4


def _hat(n: int, rng, open_=False) -> np.ndarray:
    t = np.arange(n) / SR
    noise = np.diff(np.diff(rng.standard_normal(n + 2)))   # aún más agudo
    return noise * np.exp(-t * (14 if open_ else 60)) * 0.022


def _place(buf: np.ndarray, sig: np.ndarray, start: int, gain: float = 1.0) -> None:
    if start >= len(buf):
        return
    end = min(len(buf), start + len(sig))
    buf[start:end] += sig[: end - start] * gain


def _delay(x: np.ndarray, seconds: float, feedback: float, mix: float) -> np.ndarray:
    d = int(seconds * SR)
    out = x.copy()
    tap = x.copy()
    for _ in range(4):
        tap = np.concatenate([np.zeros(d), tap[:-d]]) * feedback
        out += tap * mix
    return out


def _reverb(x: np.ndarray, mix: float = 0.18) -> np.ndarray:
    out = x.copy()
    for ms, g in ((29, .5), (37, .45), (43, .4), (53, .35), (67, .3), (79, .25)):
        d = int(ms / 1000 * SR)
        out[d:] += x[:-d] * g * mix
    return out


def render(style: str, seconds: float, seed: int = 0, accents: tuple[float, ...] = ()) -> bytes:
    """WAV estéreo de `seconds` segundos. `accents`: instantes (s) con un golpe de platillo
    suave para marcar cambios de escena."""
    st = STYLES[style]
    rng = np.random.default_rng(seed)
    bpm = rng.integers(st.bpm[0], st.bpm[1] + 1)
    step = 60 / bpm / 4                       # semicorchea
    n = int(seconds * SR)
    tonic = 45 + int(rng.integers(0, 12))     # La1..Sol#2 para el bajo
    prog = PROGRESSIONS[st.mode][int(rng.integers(0, len(PROGRESSIONS[st.mode])))]
    scale = st.scale

    def degree_midi(deg: int, octave: int) -> int:
        return tonic + 12 * octave + scale[deg % 7] + 12 * (deg // 7)

    drums = np.zeros(n)
    bass = np.zeros(n)
    chords = np.zeros(n)
    lead = np.zeros(n)
    steps_total = int(seconds / step) + 1
    intro = 0 if rng.random() < 0.5 else 8   # a veces la batería entra a la mitad del compás
    last_lead = degree_midi(0, 2)
    for i in range(steps_total):
        bar_step = i % 16
        swing = st.swing * step if bar_step % 2 else 0.0
        t0 = int((i * step + swing) * SR)
        chord_deg = prog[(i // 16) % len(prog)]
        if i >= intro:
            if st.kick[bar_step] == "x":
                _place(drums, _kick(int(0.35 * SR)), t0, 0.9)
            if st.snare[bar_step] == "x":
                _place(drums, _snare(int(0.25 * SR), rng, clap=style in ("house", "indie", "dembow")), t0, 0.8)
            if st.hat[bar_step] == "x":
                accent = 1.0 if bar_step % 4 == 2 else 0.6
                _place(drums, _hat(int(0.12 * SR), rng, open_=(style == "house" and bar_step % 4 == 2)), t0, accent)
        if st.bass[bar_step] in "xo":
            m = degree_midi(chord_deg, 0) + (7 if st.bass[bar_step] == "o" else 0)
            dur = int(step * 2.2 * SR)
            sig = _tone(_midi_hz(m), dur, "pluck" if style != "lofi" else "keys", 0.3, rng) * _env(dur, .005, .35)
            sub = np.sin(2 * np.pi * _midi_hz(m) * np.arange(dur) / SR) * _env(dur, .005, .4)
            _place(bass, sig * 0.5 + sub * 0.7, t0)
        if st.chord_rhythm[bar_step] == "x":
            dur = int(step * (8 if st.timbre in ("keys", "saw") else 3) * SR)
            notes = [degree_midi(chord_deg + k, 2) for k in (0, 2, 4)] + [degree_midi(chord_deg + 6, 2)] * (style == "lofi")
            sig = sum(_tone(_midi_hz(mm), dur, st.timbre, st.brightness, rng) for mm in notes) / len(notes)
            decay = 0.9 if st.timbre in ("keys", "saw") else 0.25
            _place(chords, sig * _env(dur, .01, decay), t0, 0.55)
        if bar_step % 2 == 0 and rng.random() < st.lead and i >= 4:
            cands = [degree_midi(chord_deg + k, 3) for k in (0, 2, 4, 7)]
            m = min(cands, key=lambda c: abs(c - last_lead) + rng.uniform(0, 6))
            last_lead = m
            dur = int(step * 2.5 * SR)
            sig = _tone(_midi_hz(m), dur, "marimba" if style == "afro" else "pluck", st.brightness, rng)
            _place(lead, sig * _env(dur, .004, .22), t0, 0.32)
    for a in accents:   # platillo suave en los cambios de escena
        crash = np.diff(rng.standard_normal(int(1.4 * SR) + 1)) * _env(int(1.4 * SR), .002, .5) * 0.025
        _place(drums, crash, int(a * SR))

    lead = _delay(lead, step * 3, 0.35, 0.5)
    chords = _reverb(chords, 0.25)
    if st.vinyl:
        crackle = (rng.random(n) > 0.9993) * rng.uniform(-0.3, 0.3, n)
        chords += crackle * 0.4 + rng.standard_normal(n) * 0.004
    # «sidechain»: el acorde y el bajo se apartan un poco en cada bombo
    duck = np.ones(n)
    for i in range(intro, steps_total):
        if st.kick[i % 16] == "x":
            s = int(i * step * SR)
            ln = min(int(0.18 * SR), n - s)
            if ln > 0:
                duck[s:s + ln] = np.minimum(duck[s:s + ln], 0.45 + 0.55 * np.linspace(0, 1, ln))
    left = drums * 0.9 + bass * duck * 0.8 + chords * duck * 0.75 + lead * 0.8
    right = drums * 0.9 + bass * duck * 0.8 + chords * duck * 0.68 + _delay(lead, 0.011, 0, 1) * 0.8
    stereo = np.stack([left, right], axis=1)
    fade = np.ones(n)
    fi, fo = int(0.05 * SR), int(0.9 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    stereo *= fade[:, None]
    peak = np.max(np.abs(stereo)) or 1.0
    stereo = np.tanh(stereo / peak * 1.4) * 0.85     # saturación suave y volumen
    pcm = (stereo * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()
