"""Tests del chat del mapa (docs/chatbot_mapa.md). LLM_PROVIDER=fake ya viene fijado por
conftest.py (sin red, sin tokens). Las funciones de app.db.repository que toca app.llm.chat
se sustituyen con monkeypatch por unos stubs en memoria (mismo espíritu que 'fake' para el
proveedor LLM): así el flujo se prueba entero sin depender de una Postgres real, igual que
el resto de la suite (ningún test existente toca la BD)."""
import asyncio
from datetime import date

import pytest

from app.db import repository as repo
from app.llm import chat as chat_llm


def _row(identifier, **kw):
    base = dict(
        identifier=identifier, title="Curso de ejemplo", type="TRAINING_COURSE",
        location="Roma", country_code="IT", start_date=date(2026, 10, 11),
        end_date=date(2026, 10, 18), application_deadline=date(2026, 8, 1),
        participant_min_age=18, participant_max_age=None, cost=None,
        topic="medio ambiente, non-formal education", summary="Un curso sobre medio ambiente.",
    )
    base.update(kw)
    return base


@pytest.fixture(autouse=True)
def _reset_catalog_cache():
    """La caché en memoria del catálogo no debe filtrarse de un test a otro."""
    chat_llm._catalog_cache.update(text=None, ids=frozenset(), built_at=0.0)
    yield
    chat_llm._catalog_cache.update(text=None, ids=frozenset(), built_at=0.0)


@pytest.fixture
def stub_repo(monkeypatch):
    """Sustituye por stubs en memoria las funciones de repository que usa app.llm.chat,
    para no necesitar una Postgres real en la suite."""
    state = {"rows": [], "counter": 0, "usage": {}}

    async def list_open():
        return state["rows"]

    async def bump_chat_query_counter():
        state["counter"] += 1

    async def get_chat_usage(month):
        return state["usage"].get(month)

    async def add_chat_usage(month, cost_usd):
        u = state["usage"].setdefault(month, {"spent_usd": 0.0, "queries": 0, "alerted": False})
        u["spent_usd"] += cost_usd
        u["queries"] += 1
        return dict(u)

    async def mark_chat_alerted(month):
        u = state["usage"].setdefault(month, {"spent_usd": 0.0, "queries": 0, "alerted": False})
        u["alerted"] = True

    monkeypatch.setattr(repo, "list_open", list_open)
    monkeypatch.setattr(repo, "bump_chat_query_counter", bump_chat_query_counter)
    monkeypatch.setattr(repo, "get_chat_usage", get_chat_usage)
    monkeypatch.setattr(repo, "add_chat_usage", add_chat_usage)
    monkeypatch.setattr(repo, "mark_chat_alerted", mark_chat_alerted)
    return state


# ── Catálogo compacto ────────────────────────────────────────────────────────────────────
def test_catalog_line_includes_age_when_only_min_known():
    line = chat_llm._catalog_line(_row("CORRADI-2026-0001", participant_max_age=None))
    assert "CORRADI-2026-0001" in line
    assert "edad 18+" in line


def test_catalog_line_no_age_data_at_all():
    line = chat_llm._catalog_line(_row("CORRADI-2026-0002", participant_min_age=None, participant_max_age=None))
    assert "edad no especificada" in line


def test_catalog_line_appends_summary_on_second_line():
    line = chat_llm._catalog_line(_row("CORRADI-2026-0003"))
    assert line.splitlines()[-1] == "Un curso sobre medio ambiente."


def test_cost_label():
    assert chat_llm._cost_label({"cost": 0}) == "gratis"
    assert chat_llm._cost_label({"cost": 25}) == "25 €"
    assert chat_llm._cost_label({"cost": None}) == "coste no especificado"


def test_next_month_label_wraps_december():
    assert chat_llm._next_month_label("2026-12") == "1 de enero"
    assert chat_llm._next_month_label("2026-07") == "1 de agosto"


# ── Coste real a partir de usage_metadata (docs/chatbot_mapa.md §3) ─────────────────────
class _Usage:
    def __init__(self, prompt_token_count, candidates_token_count):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


def test_cost_usd_matches_flash_lite_pricing():
    # cfg.llm_model por defecto es gemini-2.5-flash-lite: 0,10 $/1M entrada, 0,40 $/1M salida.
    usage = _Usage(prompt_token_count=1_000_000, candidates_token_count=1_000_000)
    assert chat_llm._cost_usd(usage) == pytest.approx(0.10 + 0.40)


def test_cost_usd_zero_without_usage_metadata():
    assert chat_llm._cost_usd(None) == 0.0


# ── status() / presupuesto ───────────────────────────────────────────────────────────────
class _FakeCfg:
    """cfg es un dataclass frozen: para simular llm_provider='gemini' (y así probar el
    corte de presupuesto, que con 'fake' siempre se salta) hace falta sustituir el objeto
    entero en vez de mutar un atributo."""
    llm_provider = "gemini"
    llm_model = "gemini-2.5-flash-lite"
    chat_monthly_budget_usd = 5.0
    chat_catalog_cache_seconds = 180


def test_status_unavailable_when_budget_exceeded(stub_repo, monkeypatch):
    monkeypatch.setattr(chat_llm, "cfg", _FakeCfg())
    month = chat_llm._current_month()
    stub_repo["usage"][month] = {"spent_usd": 10.0, "queries": 50, "alerted": False}

    result = asyncio.run(chat_llm.status())

    assert result["disponible"] is False
    assert "presupuesto" in result["motivo"].lower()


def test_status_available_under_budget(stub_repo, monkeypatch):
    monkeypatch.setattr(chat_llm, "cfg", _FakeCfg())
    month = chat_llm._current_month()
    stub_repo["usage"][month] = {"spent_usd": 0.5, "queries": 3, "alerted": False}

    result = asyncio.run(chat_llm.status())

    assert result["disponible"] is True
    assert result["motivo"] is None


def test_status_always_available_with_fake_provider(stub_repo):
    # cfg real (LLM_PROVIDER=fake de conftest.py): nunca se corta, aunque haya gasto guardado.
    month = chat_llm._current_month()
    stub_repo["usage"][month] = {"spent_usd": 999.0, "queries": 999, "alerted": False}
    assert asyncio.run(chat_llm.status()) == {"disponible": True, "motivo": None}


# ── ask() — flujo completo con el proveedor 'fake' ───────────────────────────────────────
def test_ask_returns_only_real_open_ids(stub_repo):
    stub_repo["rows"] = [_row("CORRADI-2026-0001"), _row("CORRADI-2026-0002")]

    result = asyncio.run(chat_llm.ask("¿hay algo en Italia?"))

    assert result["ids"]
    assert set(result["ids"]) <= {"CORRADI-2026-0001", "CORRADI-2026-0002"}
    assert isinstance(result["respuesta"], str) and result["respuesta"]
    assert result["aviso"] is None
    assert stub_repo["counter"] == 1  # contador agregado de counters, sumado una vez


def test_ask_with_no_open_opportunities(stub_repo):
    stub_repo["rows"] = []
    result = asyncio.run(chat_llm.ask("¿qué hay en octubre?"))
    assert result["ids"] == []
    assert "no hay ninguna oportunidad abierta" in result["respuesta"]


def test_ask_discards_hallucinated_ids_not_in_catalog(stub_repo, monkeypatch):
    """Mitigación anti-alucinación nº1 (docs/chatbot_mapa.md §6): si el proveedor devuelve
    un id que no existe entre las abiertas, ask() lo descarta antes de que salga de aquí."""
    stub_repo["rows"] = [_row("CORRADI-2026-0001")]

    import app.llm.fake as fake_mod

    def fake_chat(pregunta, open_ids):  # fake.chat() es síncrono, igual que el real
        return {"respuesta": "Encontré una que encaja.", "ids": ["CORRADI-2026-9999"], "aviso": None}

    monkeypatch.setattr(fake_mod, "chat", fake_chat)

    result = asyncio.run(chat_llm.ask("¿algo gratis?"))

    assert result["ids"] == []  # el id inventado nunca sale
    assert result["respuesta"] == "Encontré una que encaja."  # la prosa sí puede quedar rara


def test_ask_truncates_long_questions(stub_repo):
    stub_repo["rows"] = [_row("CORRADI-2026-0001")]
    result = asyncio.run(chat_llm.ask("x" * 5000))
    assert result is not None  # no debe reventar con una pregunta absurdamente larga
