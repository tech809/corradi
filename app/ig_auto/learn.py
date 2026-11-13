"""Aprendizaje: cada publicación prueba una combinación de variantes y se queda con lo que
mejor funciona (epsilon-greedy por dimensión).

Puntuación de una publicación = interacción de calidad por cuenta alcanzada, premiando un
poco el alcance absoluto (lo que más empuja Instagram son guardados y compartidos):

    score = (guardados + 1,5·compartidos + comentarios + 0,3·me gusta) / max(alcance, 20)
            · (1 + log10(1 + alcance) / 3)

Una variante sin al menos `MIN_SAMPLES` resultados se explora antes de explotar.
"""
from __future__ import annotations

import math
import random
from typing import Any

EPSILON = 0.3
MIN_SAMPLES = 2

# Dimensiones de experimento por tipo de publicación. La hora es local (TIMEZONE).
DIMENSIONS: dict[str, dict[str, list[Any]]] = {
    "carousel_opp": {"hook": ["afirmacion", "pregunta"], "hour": [13, 19, 21]},
    "reel_opp": {"hook": ["afirmacion", "pregunta"], "hour": [13, 19, 21],
                 "music": ["house", "lofi", "afro", "dembow", "synthpop", "indie"]},
    "guide": {"bg": ["sage", "clay", "ink", "paper"], "hour": [12, 19, 21]},
    "summary": {"bg": ["clay", "ink", "sage"], "hour": [11, 13, 19]},
    # Reel de cada oportunidad nueva (sale al publicarse, solo en la pestaña de Reels)
    "reel_project": {"hook": ["afirmacion", "pregunta"],
                     "music": ["house", "lofi", "afro", "dembow", "synthpop", "indie"]},
    "lastcall": {"bg": ["clay", "ink"], "hour": [12, 18]},
    "reel_lastcall": {"bg": ["clay", "ink"], "hour": [19, 21],
                      "music": ["house", "afro", "dembow", "synthpop", "indie"]},
}


def score(m: dict[str, Any] | None) -> float | None:
    if not m or m.get("reach") is None:
        return None
    reach = float(m.get("reach") or 0)
    quality = (m.get("saved", 0) + 1.5 * m.get("shares", 0) + m.get("comments", 0) + 0.3 * m.get("likes", 0))
    return quality / max(reach, 20) * (1 + math.log10(1 + reach) / 3)


def arm_stats(history: list[dict[str, Any]], kind: str, dim: str) -> dict[Any, tuple[int, float]]:
    """{valor: (n, media)} con las publicaciones de `kind` que ya tienen puntuación.
    La hora se comparte entre tipos: aprende la hora con todas las publicaciones."""
    stats: dict[Any, list[float]] = {}
    for h in history:
        if h.get("score") is None:
            continue
        if dim != "hour" and h["kind"] != kind:
            continue
        v = (h.get("variant") or {}).get(dim)
        if v is not None:
            stats.setdefault(v, []).append(h["score"])
    return {k: (len(v), sum(v) / len(v)) for k, v in stats.items()}


def choose(kind: str, history: list[dict[str, Any]], rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    variant: dict[str, Any] = {}
    for dim, options in DIMENSIONS[kind].items():
        st = arm_stats(history, kind, dim)
        under = [o for o in options if st.get(o, (0, 0))[0] < MIN_SAMPLES]
        if under:
            variant[dim] = rng.choice(under)
        elif rng.random() < EPSILON:
            variant[dim] = rng.choice(options)
        else:
            variant[dim] = max(options, key=lambda o: st.get(o, (0, 0))[1])
    return variant


def summary(history: list[dict[str, Any]]) -> list[str]:
    """Líneas legibles con lo aprendido, para el informe semanal."""
    lines = []
    for kind, dims in DIMENSIONS.items():
        for dim in dims:
            st = arm_stats(history, kind, dim)
            if not st or (dim == "hour" and kind != "carousel_opp"):
                continue
            best = max(st.items(), key=lambda kv: kv[1][1])
            parts = ", ".join(f"{k}: {v[1]:.3f} (n={v[0]})" for k, v in sorted(st.items(), key=lambda kv: -kv[1][1]))
            label = "hora (todas)" if dim == "hour" else f"{kind}·{dim}"
            lines.append(f"{label} → mejor {best[0]} · {parts}")
    return lines
