"""Asistente de candidatura: convierte hechos aportados por el usuario en un borrador.

Nunca completa huecos con experiencia supuesta. El contrato de salida es deliberadamente
pequeño para que el frontend pueda degradar con elegancia si el proveedor no está activo.
"""
from __future__ import annotations

import json
from typing import Any

from app.config import cfg


TASK_LABELS = {
    "motivation": "una respuesta sobre su motivación para participar",
    "why_me": "una respuesta sobre qué puede aportar al grupo",
    "experience": "una respuesta que presente su experiencia relevante",
    "review": "una versión revisada del borrador aportado",
}


def _clean(value: Any, limit: int = 1800) -> str:
    return " ".join(str(value or "").split())[:limit]


def build_prompt(project: dict[str, Any], data: dict[str, Any]) -> str:
    facts = {
        "title": _clean(project.get("title"), 240),
        "type": _clean(project.get("type"), 80),
        "topic": _clean(project.get("topic"), 500),
        "summary": _clean(project.get("summary"), 1000),
        "participant_profile": _clean(project.get("participant_profile"), 1000),
        "learning_outcomes": _clean(project.get("learning_outcomes"), 1000),
    }
    user = {key: _clean(data.get(key)) for key in (
        "draft", "motivation", "experience", "strengths", "languages"
    )}
    return f"""Eres un editor de candidaturas Erasmus+ en español.
Redacta {TASK_LABELS[data['task']]} para esta oportunidad.

OPORTUNIDAD (datos verificados):
{json.dumps(facts, ensure_ascii=False)}

DATOS APORTADOS POR LA PERSONA:
{json.dumps(user, ensure_ascii=False)}

Reglas obligatorias:
- No inventes experiencias, capacidades, idiomas, resultados ni motivaciones.
- Si falta un dato necesario, deja [añade aquí ...] en vez de asumirlo.
- Voz natural, concreta y personal; evita grandilocuencia y frases vacías.
- Entre 100 y 180 palabras, salvo que solo estés revisando un texto más corto.
- Devuelve JSON con las claves draft y tips. tips contiene 2 o 3 consejos breves.
"""


def _fake_result(project: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    title = _clean(project.get("title"), 180) or "este proyecto"
    topic = _clean(project.get("topic"), 180) or "su temática"
    motivation = _clean(data.get("motivation"), 500)
    experience = _clean(data.get("experience"), 500)
    strengths = _clean(data.get("strengths"), 500)
    draft = _clean(data.get("draft"), 1800)
    if data.get("task") == "review" and draft:
        text = draft
    else:
        text = (
            f"Quiero participar en {title} porque {motivation or '[explica aquí tu motivación concreta]'}. "
            f"Me interesa especialmente {topic} y espero aprender cómo aplicar estas ideas en mi entorno. "
            f"Mi experiencia relacionada es {experience or '[añade una experiencia real, aunque sea pequeña]'}. "
            f"También puedo aportar {strengths or '[indica una fortaleza o forma de contribuir al grupo]'}. "
            "Me gustaría compartir lo aprendido después del proyecto y convertirlo en acciones concretas."
        )
    return {
        "draft": text,
        "tips": [
            "Sustituye todos los corchetes con hechos propios.",
            "Añade un ejemplo concreto y evita afirmar algo que no puedas explicar.",
        ],
        "notice": "Borrador orientativo: revísalo y haz que suene a ti antes de enviarlo.",
    }


async def assist(project: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    if cfg.llm_provider == "fake":
        return _fake_result(project, data)

    from google.genai import types
    from app.llm import chat as chat_llm
    from app.llm.retry import with_retry

    status = await chat_llm.status()
    if not status["disponible"]:
        return {"draft": "", "tips": [], "notice": status["motivo"]}
    try:
        response = with_retry(
            lambda: chat_llm._gemini_client().models.generate_content(
                model=cfg.llm_model,
                contents=build_prompt(project, data),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.35,
                    max_output_tokens=900,
                ),
            ),
            attempts=2,
        )
        await chat_llm._record_usage(response)
        result = json.loads(chat_llm._strip_fences(response.text))
        if not isinstance(result, dict):
            raise ValueError("invalid response")
        return {
            "draft": _clean(result.get("draft"), 5000),
            "tips": [_clean(x, 240) for x in (result.get("tips") or [])[:3]],
            "notice": "Borrador orientativo: revísalo y haz que suene a ti antes de enviarlo.",
        }
    except Exception:
        return _fake_result(project, data)
