"""Soporte de servidor para la app móvil: registro push, resumen diario, enlaces universales,
página de privacidad y banner «Descarga la app»."""
import asyncio
import dataclasses
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.db import repository as repo
from app.scheduler import push_digest

TOKEN = "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"
NOW = datetime(2026, 11, 13, 18, 30, tzinfo=timezone.utc)
FP = ":".join(["AB"] * 32)


@pytest.fixture
def client():
    # Sin `with`: no se ejecuta el lifespan (no abre el pool de la BD).
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    main._push_hits.clear()
    yield
    main._push_hits.clear()


@pytest.fixture
def devices(monkeypatch):
    """Tabla push_devices simulada en memoria."""
    table: dict[str, dict] = {}

    async def upsert(token, platform, types, daily_digest):
        table[token] = {"token": token, "platform": platform, "types": types, "daily_digest": daily_digest}

    async def delete(tokens):
        n = 0
        for t in tokens:
            n += table.pop(t, None) is not None
        return n

    async def list_digest():
        return [d for d in table.values() if d["daily_digest"]]

    monkeypatch.setattr(repo, "upsert_push_device", upsert)
    monkeypatch.setattr(repo, "delete_push_devices", delete)
    monkeypatch.setattr(repo, "list_push_digest_devices", list_digest)
    return table


def _cfg(monkeypatch, **values):
    monkeypatch.setattr(main, "cfg", dataclasses.replace(main.cfg, **values))


# ── /api/push/register y /unregister ──────────────────────────────────────────────────

def test_register_upserts_and_normalises_types(client, devices):
    r = client.post("/api/push/register", json={
        "token": TOKEN, "platform": "ios",
        "types": ["VOLUNTEERING", "YOUTH_EXCHANGE", "VOLUNTEERING"], "daily_digest": True,
    })
    assert r.status_code == 200
    assert devices[TOKEN]["types"] == ["YOUTH_EXCHANGE", "VOLUNTEERING"]
    # Segunda llamada con el mismo token = actualización, no fila nueva.
    client.post("/api/push/register", json={"token": TOKEN, "platform": "ios", "types": [], "daily_digest": False})
    assert len(devices) == 1
    assert devices[TOKEN]["types"] == [] and devices[TOKEN]["daily_digest"] is False


def test_register_accepts_both_expo_token_prefixes(client, devices):
    r = client.post("/api/push/register", json={"token": "ExpoPushToken[abcDEF123_-xyz]", "platform": "android"})
    assert r.status_code == 200
    assert devices["ExpoPushToken[abcDEF123_-xyz]"]["daily_digest"] is True  # por defecto


@pytest.mark.parametrize("payload", [
    {"token": "hola", "platform": "ios"},
    {"token": "ExponentPushToken[]", "platform": "ios"},
    {"token": "ExponentPushToken[" + "a" * 300 + "]", "platform": "ios"},
    {"token": "ExponentPushToken[abc def ghi]", "platform": "ios"},
    {"token": "<script>ExponentPushToken[abcdefghij]", "platform": "ios"},
    {"token": TOKEN, "platform": "web"},
    {"token": TOKEN, "platform": "ios", "types": ["ESC"]},
    {"token": TOKEN, "platform": "ios", "types": ["YOUTH_EXCHANGE"] * 4},
    {"platform": "ios"},
])
def test_register_rejects_junk_with_422(client, devices, payload):
    assert client.post("/api/push/register", json=payload).status_code == 422
    assert devices == {}


def test_unregister_deletes_token(client, devices):
    client.post("/api/push/register", json={"token": TOKEN, "platform": "ios"})
    assert client.post("/api/push/unregister", json={"token": TOKEN}).status_code == 200
    assert devices == {}
    # Repetir la baja no falla ni revela nada.
    assert client.post("/api/push/unregister", json={"token": TOKEN}).json() == {"ok": "1"}
    assert client.post("/api/push/unregister", json={"token": "basura"}).status_code == 422


def test_register_is_rate_limited_per_ip(client, devices):
    for _ in range(main._PUSH_RATE_LIMIT_PER_HOUR):
        assert client.post("/api/push/register", json={"token": TOKEN, "platform": "ios"}).status_code == 200
    assert client.post("/api/push/register", json={"token": TOKEN, "platform": "ios"}).status_code == 429
    other = {"X-Forwarded-For": "203.0.113.9"}
    assert client.post("/api/push/register", json={"token": TOKEN, "platform": "ios"}, headers=other).status_code == 200


def test_push_rate_limit_is_generous_for_shared_ips():
    # NAT de operadora / wifi de campus: muchos usuarios reales detrás de una IP.
    assert main._PUSH_RATE_LIMIT_PER_HOUR == 120
    assert main._PUSH_RATE_LIMIT_PER_DAY == 600


def test_push_daily_limit_and_unregister_share_window(client, devices, monkeypatch):
    monkeypatch.setattr(main, "_PUSH_RATE_LIMIT_PER_DAY", 3)
    assert client.post("/api/push/register", json={"token": TOKEN, "platform": "ios"}).status_code == 200
    assert client.post("/api/push/unregister", json={"token": TOKEN}).status_code == 200
    assert client.post("/api/push/register", json={"token": TOKEN, "platform": "ios"}).status_code == 200
    assert client.post("/api/push/unregister", json={"token": TOKEN}).status_code == 429


# ── Resumen diario push ───────────────────────────────────────────────────────────────

def _project(identifier, type_, hours_ago, title=None):
    return {
        "identifier": identifier, "title": title or f"Proyecto {identifier}", "type": type_,
        "status": "open", "application_deadline": date(2026, 12, 1),
        "created": NOW - timedelta(hours=hours_ago),
    }


@pytest.fixture
def tickets_table(monkeypatch, devices):
    """Tabla push_tickets simulada + baja condicionada por last_seen_at."""
    table: dict[str, dict] = {}
    removed_pairs: list = []

    async def save(rows, created_at):
        for ticket_id, token in rows:
            table.setdefault(ticket_id, {"ticket_id": ticket_id, "token": token, "created_at": created_at})

    async def list_before(before):
        return sorted((t for t in table.values() if t["created_at"] <= before), key=lambda t: t["created_at"])

    async def delete(ids):
        return sum(table.pop(i, None) is not None for i in ids)

    async def purge(before):
        old = [i for i, t in table.items() if t["created_at"] < before]
        for i in old:
            del table[i]
        return len(old)

    async def delete_unseen(pairs):
        removed_pairs.extend(pairs)
        n = 0
        for token, _sent in pairs:
            n += devices.pop(token, None) is not None
        return n

    monkeypatch.setattr(repo, "save_push_tickets", save)
    monkeypatch.setattr(repo, "list_push_tickets_before", list_before)
    monkeypatch.setattr(repo, "delete_push_tickets", delete)
    monkeypatch.setattr(repo, "purge_push_tickets", purge)
    monkeypatch.setattr(repo, "delete_push_devices_not_seen_since", delete_unseen)
    return table, removed_pairs


@pytest.fixture
def digest_env(monkeypatch, devices, tickets_table):
    state = {"last": None, "runs": [], "projects": [], "sent": [], "tickets": tickets_table[0]}

    async def last():
        return state["last"]

    async def record(sent_at, project_count, device_count):
        state["runs"].append((sent_at, project_count, device_count))

    async def list_open():
        return state["projects"]

    monkeypatch.setattr(repo, "last_push_digest_at", last)
    monkeypatch.setattr(repo, "record_push_digest_run", record)
    monkeypatch.setattr(repo, "list_open", list_open)

    async def ok_sender(batch):
        start = len(state["sent"])
        state["sent"].extend(batch)
        return [{"status": "ok", "id": f"r{start + i}"} for i, _ in enumerate(batch)]

    async def no_receipts(_ids):
        return {}

    state["sender"] = ok_sender
    state["fetch"] = no_receipts
    return state


def _add(devices, token, types=(), daily=True):
    devices[token] = {"token": token, "platform": "ios", "types": list(types), "daily_digest": daily}


def test_digest_first_run_uses_last_24h_and_filters_by_type(digest_env, devices):
    digest_env["projects"] = [
        _project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 2, "Clima en Roma"),
        _project("CORRADI-2026-0002", "TRAINING_COURSE", 5, "Formación en Lisboa"),
        _project("CORRADI-2026-0003", "YOUTH_EXCHANGE", 10, "Arte en Atenas"),
        _project("CORRADI-2026-0004", "YOUTH_EXCHANGE", 30),  # más de 24 h: fuera
    ]
    _add(devices, "ExponentPushToken[all00000000]")
    _add(devices, "ExponentPushToken[ye000000000]", ["YOUTH_EXCHANGE"])
    _add(devices, "ExponentPushToken[esc00000000]", ["VOLUNTEERING"])        # 0 coincidencias
    _add(devices, "ExponentPushToken[off00000000]", daily=False)            # sin resumen

    stats = asyncio.run(push_digest.digest(now=NOW, send=digest_env["sender"]))

    by_token = {m["to"]: m for m in digest_env["sent"]}
    assert set(by_token) == {"ExponentPushToken[all00000000]", "ExponentPushToken[ye000000000]"}
    everything = by_token["ExponentPushToken[all00000000]"]
    assert everything["title"] == "Hay 3 proyectos nuevos para ti"
    assert everything["body"] == "Clima en Roma · Formación en Lisboa y 1 más"
    assert everything["sound"] == "default"
    assert everything["data"] == {
        "screen": "nuevos", "ids": ["CORRADI-2026-0001", "CORRADI-2026-0002", "CORRADI-2026-0003"],
    }
    assert everything["channelId"] == "digest"
    ye = by_token["ExponentPushToken[ye000000000]"]
    assert ye["title"] == "Hay 2 proyectos nuevos para ti"
    assert ye["body"] == "Clima en Roma · Arte en Atenas"
    # Solo los ids que cuenta su notificación (tras el filtro de tipos).
    assert ye["data"]["ids"] == ["CORRADI-2026-0001", "CORRADI-2026-0003"]
    assert stats["projects"] == 3 and stats["devices"] == 2
    assert digest_env["runs"] == [(NOW, 3, 2)]


def test_digest_only_counts_projects_since_last_run(digest_env, devices):
    digest_env["last"] = NOW - timedelta(hours=3)
    digest_env["projects"] = [
        _project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1, "Nuevo"),
        _project("CORRADI-2026-0002", "YOUTH_EXCHANGE", 4, "Ya avisado"),
    ]
    _add(devices, TOKEN)
    asyncio.run(push_digest.digest(now=NOW, send=digest_env["sender"]))
    assert [m["title"] for m in digest_env["sent"]] == ["Hay 1 proyecto nuevo para ti"]
    assert digest_env["sent"][0]["body"] == "Nuevo"
    assert digest_env["sent"][0]["data"]["ids"] == ["CORRADI-2026-0001"]


def test_digest_nothing_new_sends_nothing_but_records_run(digest_env, devices):
    digest_env["last"] = NOW - timedelta(hours=1)
    digest_env["projects"] = [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 5)]
    _add(devices, TOKEN)

    async def boom(_batch):
        raise AssertionError("no debería enviarse nada")

    stats = asyncio.run(push_digest.digest(now=NOW, send=boom))
    assert stats["projects"] == 0
    assert digest_env["runs"] == [(NOW, 0, 0)]


def test_digest_removes_device_not_registered_and_keeps_others(digest_env, devices):
    digest_env["projects"] = [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1)]
    _add(devices, "ExponentPushToken[alive000000]")
    _add(devices, "ExponentPushToken[dead0000000]")
    _add(devices, "ExponentPushToken[other000000]")

    async def sender(batch):
        tickets = []
        for m in batch:
            if "dead" in m["to"]:
                tickets.append({"status": "error", "message": "not registered",
                                "details": {"error": "DeviceNotRegistered"}})
            elif "other" in m["to"]:
                tickets.append({"status": "error", "message": "rate", "details": {"error": "MessageRateExceeded"}})
            else:
                tickets.append({"status": "ok", "id": "x"})
        return tickets

    stats = asyncio.run(push_digest.digest(now=NOW, send=sender))
    assert set(devices) == {"ExponentPushToken[alive000000]", "ExponentPushToken[other000000]"}
    assert stats == {"projects": 1, "devices": 3, "sent": 1, "errors": 2, "removed": 1}


def test_digest_batches_of_100(digest_env, devices):
    digest_env["projects"] = [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1)]
    for i in range(250):
        _add(devices, f"ExponentPushToken[tok{i:08d}]")
    sizes = []

    async def sender(batch):
        sizes.append(len(batch))
        return [{"status": "ok"} for _ in batch]

    asyncio.run(push_digest.digest(now=NOW, send=sender))
    assert sizes == [100, 100, 50]


def test_digest_all_batches_failed_does_not_record_run(digest_env, devices):
    digest_env["projects"] = [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1)]
    _add(devices, TOKEN)

    async def down(_batch):
        raise push_digest.ExpoRequestError("HTTP 503")

    with pytest.raises(push_digest.ExpoRequestError):
        asyncio.run(push_digest.digest(now=NOW, send=down))
    assert digest_env["runs"] == []  # mañana se reintenta con los mismos proyectos


def test_expo_send_request_format(monkeypatch):
    seen = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"status": "ok", "id": "abc"}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json, headers):
            seen.update(url=url, json=json, headers=headers)
            return FakeResponse()

    monkeypatch.setattr(push_digest.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(push_digest, "cfg", dataclasses.replace(push_digest.cfg, expo_access_token="secreto"))
    msg = push_digest.build_message(TOKEN, [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1, "Uno")])
    tickets = asyncio.run(push_digest.expo_send([msg]))
    assert tickets == [{"status": "ok", "id": "abc"}]
    assert seen["url"] == "https://exp.host/--/api/v2/push/send"
    assert seen["json"] == [msg]
    assert seen["headers"]["Authorization"] == "Bearer secreto"
    assert seen["headers"]["Content-Type"] == "application/json"


def test_digest_copy_cleans_titles():
    projects = [
        _project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1, "❗🌍 YOUTH EXCHANGE | CLIMA Y MONTAÑA ✨"),
        _project("CORRADI-2026-0002", "TRAINING_COURSE", 2, "Formación en Lisboa  |  Arte urbano 🎨"),
        _project("CORRADI-2026-0003", "VOLUNTEERING", 3, "Otro"),
        _project("CORRADI-2026-0004", "VOLUNTEERING", 4, "Y otro"),
    ]
    msg = push_digest.build_message(TOKEN, projects)
    assert msg["title"] == "Hay 4 proyectos nuevos para ti"
    assert msg["body"] == "YOUTH EXCHANGE · CLIMA Y MONTAÑA · Formación en Lisboa · Arte urbano y 2 más"
    one = push_digest.build_message(TOKEN, projects[1:2])
    assert one["title"] == "Hay 1 proyecto nuevo para ti"
    assert one["body"] == "Formación en Lisboa · Arte urbano"


@pytest.mark.parametrize("raw, clean", [
    ("❗ESC en Polonia❗", "ESC en Polonia"),           # mayúsculas sueltas: se respetan
    ("🇵🇹 Proyecto en Oporto", "Proyecto en Oporto"),
    ("| Título |", "Título"),
    ("🔥🔥", "(sin título)"),
    (None, "(sin título)"),
    ("TC: INCLUSIÓN DIGITAL EN ROMA", "TC: INCLUSIÓN DIGITAL EN ROMA"),
])
def test_clean_title(raw, clean):
    assert push_digest._clean_title(raw) == clean


def test_digest_ids_capped_and_payload_well_under_4kb():
    projects = [_project(f"CORRADI-2026-{i:04d}", "YOUTH_EXCHANGE", 1, "Título muy largo " * 10)
                for i in range(200)]
    msg = push_digest.build_message("ExponentPushToken[" + "a" * 200 + "]", projects)
    assert len(msg["data"]["ids"]) == push_digest.MAX_IDS == 50
    assert msg["data"]["ids"][0] == "CORRADI-2026-0000"
    assert msg["title"] == "Hay 200 proyectos nuevos para ti"
    assert len(json.dumps(msg, ensure_ascii=False).encode()) < 2500


# ── Recibos (getReceipts) ─────────────────────────────────────────────────────────────

def test_digest_saves_accepted_tickets(digest_env, devices):
    digest_env["projects"] = [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1)]
    _add(devices, "ExponentPushToken[alive000000]")
    _add(devices, "ExponentPushToken[dead0000000]")

    async def sender(batch):
        return [{"status": "ok", "id": "tk-alive"} if "alive" in m["to"] else
                {"status": "error", "details": {"error": "DeviceNotRegistered"}} for m in batch]

    asyncio.run(push_digest.digest(now=NOW, send=sender))
    assert digest_env["tickets"] == {
        "tk-alive": {"ticket_id": "tk-alive", "token": "ExponentPushToken[alive000000]", "created_at": NOW},
    }


def test_check_receipts_removes_dead_tokens_and_cleans_tickets(tickets_table, devices, caplog):
    table, removed = tickets_table
    for name in ("ok", "dead", "big", "pending"):
        _add(devices, f"ExponentPushToken[{name}00000000]")
    sent_at = NOW - timedelta(minutes=30)
    asyncio.run(repo.save_push_tickets([
        ("t-ok", "ExponentPushToken[ok00000000]"),
        ("t-dead", "ExponentPushToken[dead00000000]"),
        ("t-big", "ExponentPushToken[big00000000]"),
        ("t-pending", "ExponentPushToken[pending00000000]"),
    ], sent_at))
    asyncio.run(repo.save_push_tickets([("t-fresh", "ExponentPushToken[ok00000000]")], NOW - timedelta(minutes=5)))
    asyncio.run(repo.save_push_tickets([("t-old", "ExponentPushToken[ok00000000]")], NOW - timedelta(hours=49)))
    asked = []

    async def fetch(ids):
        asked.append(list(ids))
        return {
            "t-ok": {"status": "ok"},
            "t-dead": {"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}},
            "t-big": {"status": "error", "message": "too big", "details": {"error": "MessageTooBig"}},
            # t-pending y t-old: sin recibo
        }

    with caplog.at_level("WARNING", logger="corradi.push_digest"):
        stats = asyncio.run(push_digest.check_receipts(NOW, fetch))
    # Solo se piden los de más de 15 min (t-fresh espera a la siguiente pasada).
    assert sorted(asked[0]) == ["t-big", "t-dead", "t-ok", "t-old", "t-pending"]
    assert removed == [("ExponentPushToken[dead00000000]", sent_at)]
    assert "ExponentPushToken[dead00000000]" not in devices
    assert "ExponentPushToken[big00000000]" in devices
    assert "MessageTooBig" in caplog.text
    # Procesados y caducados fuera; quedan el pendiente y el reciente.
    assert set(table) == {"t-pending", "t-fresh"}
    assert stats == {"tickets": 5, "ok": 1, "errors": 2, "removed": 1, "missing": 2, "purged": 1}


def test_check_receipts_batches_of_1000_and_keeps_failed_batch(tickets_table, devices):
    table, _ = tickets_table
    asyncio.run(repo.save_push_tickets(
        [(f"t{i:05d}", TOKEN) for i in range(2500)], NOW - timedelta(hours=1)))
    sizes = []

    async def fetch(ids):
        sizes.append(len(ids))
        if len(sizes) == 2:
            raise push_digest.ExpoRequestError("HTTP 503")
        return {i: {"status": "ok"} for i in ids}

    stats = asyncio.run(push_digest.check_receipts(NOW, fetch))
    assert sizes == [1000, 1000, 500]
    assert len(table) == 1000  # el lote que falló se reintenta en la siguiente pasada
    assert stats["ok"] == 1500


def test_digest_checks_receipts_first(digest_env, devices):
    _add(devices, "ExponentPushToken[dead0000000]")
    asyncio.run(repo.save_push_tickets([("t1", "ExponentPushToken[dead0000000]")], NOW - timedelta(hours=1)))
    digest_env["projects"] = [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1)]

    async def fetch(ids):
        return {"t1": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}

    stats = asyncio.run(push_digest.digest(now=NOW, send=digest_env["sender"], fetch_receipts=fetch))
    assert digest_env["sent"] == [] and stats["devices"] == 0


def test_digest_survives_receipts_failure(digest_env, devices, monkeypatch):
    async def broken(_before):
        raise RuntimeError("BD caída")
    monkeypatch.setattr(repo, "list_push_tickets_before", broken)
    digest_env["projects"] = [_project("CORRADI-2026-0001", "YOUTH_EXCHANGE", 1)]
    _add(devices, TOKEN)
    stats = asyncio.run(push_digest.digest(now=NOW, send=digest_env["sender"]))
    assert stats["sent"] == 1


def test_receipts_only_run_skips_digest(monkeypatch):
    calls = []

    async def noop():
        calls.append("pool")

    async def receipts(*a, **k):
        calls.append("receipts")

    async def digest(*a, **k):
        calls.append("digest")

    monkeypatch.setattr(push_digest, "open_pool", noop)
    monkeypatch.setattr(push_digest, "close_pool", noop)
    monkeypatch.setattr(push_digest, "check_receipts", receipts)
    monkeypatch.setattr(push_digest, "digest", digest)
    asyncio.run(push_digest.run(receipts_only=True))
    assert calls == ["pool", "receipts", "pool"]


def test_expo_get_receipts_request_format(monkeypatch):
    seen = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"data": {"abc": {"status": "ok"}}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json, headers):
            seen.update(url=url, json=json, headers=headers)
            return FakeResponse()

    monkeypatch.setattr(push_digest.httpx, "AsyncClient", FakeClient)
    assert asyncio.run(push_digest.expo_get_receipts(["abc", "def"])) == {"abc": {"status": "ok"}}
    assert seen["url"] == "https://exp.host/--/api/v2/push/getReceipts"
    assert seen["json"] == {"ids": ["abc", "def"]}
    assert seen["headers"]["Content-Type"] == "application/json"


# ── /.well-known ──────────────────────────────────────────────────────────────────────

def test_well_known_off_without_env(client, monkeypatch):
    _cfg(monkeypatch, apple_team_id="", android_cert_sha256=[])
    assert client.get("/.well-known/apple-app-site-association").status_code == 404
    assert client.get("/.well-known/assetlinks.json").status_code == 404


def test_apple_app_site_association(client, monkeypatch):
    _cfg(monkeypatch, apple_team_id="ABCDE12345")
    r = client.get("/.well-known/apple-app-site-association", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    detail = r.json()["applinks"]["details"][0]
    assert detail["appIDs"] == ["ABCDE12345.eu.proactivefuture.corradi"]
    paths = [c["/"] for c in detail["components"]]
    assert paths == ["/proyecto/*", "/????-????"]


def test_aasa_short_link_pattern_matches_short_route():
    """El patrón AASA (`?` = un carácter) cubre exactamente la forma de _SHORT_ID_RE."""
    import fnmatch
    from app.api import main
    sample = "2026-0123"
    assert main._SHORT_ID_RE.fullmatch(sample)
    assert fnmatch.fnmatchcase("/" + sample, "/????-????")
    assert not fnmatch.fnmatchcase("/proyecto/CORRADI-" + sample, "/????-????")


def test_assetlinks(client, monkeypatch):
    _cfg(monkeypatch, android_cert_sha256=[FP, "no-es-una-huella"])
    r = client.get("/.well-known/assetlinks.json", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    [statement] = r.json()
    assert statement["relation"] == ["delegate_permission/common.handle_all_urls"]
    assert statement["target"] == {
        "namespace": "android_app", "package_name": "eu.proactivefuture.corradi",
        "sha256_cert_fingerprints": [FP],
    }
    _cfg(monkeypatch, android_cert_sha256=["no-es-una-huella"])
    assert client.get("/.well-known/assetlinks.json").status_code == 404


# ── Privacidad y banner ───────────────────────────────────────────────────────────────

def test_privacy_page_and_sitemap(client, monkeypatch):
    r = client.get("/privacidad-app")
    assert r.status_code == 200
    assert "2026-11-13" in r.text and "tech@proactivefuture.eu" in r.text
    assert "REVISIÓN LEGAL" in r.text

    async def list_open():
        return []
    monkeypatch.setattr(repo, "list_open", list_open)
    _cfg(monkeypatch, map_public_url="https://mapa.proactivefuture.eu/mapa")
    assert "https://mapa.proactivefuture.eu/privacidad-app" in client.get("/sitemap.xml").text


def _project_row():
    return {"identifier": "CORRADI-2026-0001", "title": "Clima", "type": "YOUTH_EXCHANGE",
            "status": "open", "application_deadline": date.today() + timedelta(days=5)}


@pytest.fixture
def project_repo(monkeypatch):
    async def get(identifier):
        return _project_row()
    monkeypatch.setattr(repo, "get_by_identifier", get)


@pytest.mark.parametrize("path", ["/", "/proyecto/CORRADI-2026-0001"])
def test_banner_off_without_env(client, monkeypatch, project_repo, path):
    _cfg(monkeypatch, app_store_url="", play_store_url="", app_store_id="")
    body = client.get(path).text
    assert "app-banner" not in body and "apple-itunes-app" not in body


@pytest.mark.parametrize("path", ["/", "/proyecto/CORRADI-2026-0001"])
def test_banner_on_with_env(client, monkeypatch, project_repo, path):
    _cfg(monkeypatch, app_store_url="https://apps.apple.com/app/id123456789",
         play_store_url="https://play.google.com/store/apps/details?id=eu.proactivefuture.corradi",
         app_store_id="123456789")
    r = client.get(path)
    assert r.status_code == 200
    body = r.text
    assert 'id="app-banner"' in body
    assert '<meta name="apple-itunes-app" content="app-id=123456789">' in body
    assert body.index("apple-itunes-app") < body.index("</head>")
    assert "https://apps.apple.com/app/id123456789" in body
    assert "id=eu.proactivefuture.corradi" in body
    # El ETag sigue funcionando con el contenido modificado.
    assert client.get(path, headers={"If-None-Match": r.headers["etag"]}).status_code == 304


def test_banner_only_store_id_emits_meta_without_banner(client, monkeypatch):
    _cfg(monkeypatch, app_store_url="", play_store_url="", app_store_id="123456789")
    body = client.get("/").text
    assert "apple-itunes-app" in body and 'id="app-banner"' not in body


def test_banner_ignores_non_https_urls(client, monkeypatch):
    _cfg(monkeypatch, app_store_url="javascript:alert(1)", play_store_url="", app_store_id="")
    body = client.get("/").text
    assert "app-banner" not in body and "javascript:alert" not in body
