import time

import pytest
from google.genai import errors as gerr

from app.llm.retry import with_retry

_QUOTA_JSON = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded for ..."}}
_BAD_REQ_JSON = {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "bad"}}
_SERVER_JSON = {"error": {"code": 503, "status": "UNAVAILABLE", "message": "high demand"}}


def test_devuelve_el_resultado_si_no_hay_error():
    assert with_retry(lambda: 42) == 42


def test_429_en_llamada_de_fondo_reintenta_y_luego_avisa(monkeypatch):
    waits = []
    monkeypatch.setattr(time, "sleep", lambda s: waits.append(s))
    llamadas = []

    def fn():
        llamadas.append(1)
        raise gerr.ClientError(429, _QUOTA_JSON)

    with pytest.raises(RuntimeError) as exc:
        with_retry(fn, attempts=4)          # llamada de fondo
    assert len(llamadas) == 3               # 1 + 2 reintentos
    assert waits == [35, 35]               # espera larga por el cupo por minuto
    msg = str(exc.value)
    assert msg.startswith("Problema de cuota")  # sin emoji: lo pone quien lo enseña
    assert "RESOURCE_EXHAUSTED" in msg           # el error original se conserva detrás


def test_429_en_llamada_interactiva_falla_rapido_sin_esperar(monkeypatch):
    waits = []
    monkeypatch.setattr(time, "sleep", lambda s: waits.append(s))
    llamadas = []

    def fn():
        llamadas.append(1)
        raise gerr.ClientError(429, _QUOTA_JSON)

    with pytest.raises(RuntimeError):
        with_retry(fn, attempts=2)          # el chat pasa attempts=2
    assert len(llamadas) == 1 and waits == []   # ni reintento ni espera de 35 s


def test_otros_errores_de_cliente_se_propagan_tal_cual(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    def fn():
        raise gerr.ClientError(400, _BAD_REQ_JSON)

    with pytest.raises(gerr.ClientError):
        with_retry(fn, attempts=3)


def test_los_5xx_si_se_reintentan(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    llamadas = []

    def fn():
        llamadas.append(1)
        if len(llamadas) < 3:
            raise gerr.ServerError(503, _SERVER_JSON)
        return "ok"

    assert with_retry(fn, attempts=4) == "ok"
    assert len(llamadas) == 3
