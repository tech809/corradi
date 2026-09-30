"""Contrato mínimo del Top 3 entre repositorio, API, scheduler y portada."""
from pathlib import Path
import asyncio

from fastapi import Response

from app.api import main as api_main
from app.db import repository as repo
from app.scheduler import top_projects


def test_scheduler_y_repositorio_comparten_la_consulta_top_projects():
    """Evita desplegar el scheduler nuevo con un repository antiguo."""
    assert callable(repo.list_top_projects)
    assert top_projects.repo is repo


def test_portada_carga_el_top_desde_la_api():
    html = (
        Path(__file__).parents[1] / "app" / "api" / "static" / "discover.html"
    ).read_text(encoding="utf-8")

    assert 'id="weeklyTop"' in html
    assert 'fetch("/api/top")' in html
    assert "renderWeeklyTop" in html


def test_api_top_usa_visitas_de_la_ultima_semana(monkeypatch):
    called = []

    async def fake_list_top_projects(**kwargs):
        called.append(kwargs)
        return []

    monkeypatch.setattr(api_main.repo, "list_top_projects", fake_list_top_projects)
    result = asyncio.run(api_main.top_projects(Response()))

    assert called == [{"days": 7, "limit": 9, "kinds": ("view",)}]
    assert result == {"period_days": 7, "results": []}
