"""Embeddings para la deduplicación semántica (pgvector). Gemini, o 'fake' para dry-run/tests."""
from __future__ import annotations

from app.config import cfg

_client = None


class LLMNotConfigured(RuntimeError):
    pass


def _gemini_client():
    global _client
    if _client is None:
        if not cfg.gemini_api_key:
            raise LLMNotConfigured("Falta GEMINI_API_KEY en el entorno (.env).")
        from google import genai
        _client = genai.Client(api_key=cfg.gemini_api_key)
    return _client


def embed(text: str) -> list[float]:
    if cfg.llm_provider == "fake":
        from app.llm import fake
        return fake.embed(text)

    from google.genai import types

    from app.llm.retry import with_retry

    resp = with_retry(lambda: _gemini_client().models.embed_content(
        model=cfg.embed_model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=cfg.embed_dim),
    ))
    return list(resp.embeddings[0].values)
