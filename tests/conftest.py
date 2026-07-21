"""Fija el proveedor LLM 'fake' ANTES de que se importe app.config (cfg se crea al importar)."""
import os

os.environ["LLM_PROVIDER"] = "fake"
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("EMBED_DIM", "768")
