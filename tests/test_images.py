from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app import images


def test_queries_prioritise_place_region_and_country():
    queries = images._queries({
        "location": "Manjirón, Sierra Norte de Madrid", "country_code": "ES",
        "topic": "inclusion",
    })
    assert queries[0] == "Manjirón Spain"
    assert queries[1] == "Sierra Norte de Madrid Spain"
    assert queries[2] == "Spain travel landscape"


def test_enrich_uses_stable_relevant_result(monkeypatch):
    monkeypatch.setattr(images, "cfg", SimpleNamespace(pexels_api_key="key"))
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"photos": [
                {"id": i, "photographer": f"P{i}", "url": f"https://pexels.test/{i}",
                 "alt": f"Braga Portugal city view {i}",
                 "src": {"large": f"https://img.test/{i}.jpg"}}
                for i in range(8)
            ]}

    def fake_get(_url, **kwargs):
        calls.append(kwargs["params"]["query"])
        return Response()

    monkeypatch.setattr(images.httpx, "get", fake_get)
    fields = {"title": "Same project", "location": "Braga", "country_code": "PT"}
    first = images.enrich(fields)
    second = images.enrich(fields)
    assert first["image_url"] == second["image_url"]
    assert first["image_origin"] == "pexels"
    assert calls[0] == "Braga Portugal"


def test_enrich_rejects_wrong_city_and_falls_back_to_country(monkeypatch):
    monkeypatch.setattr(images, "cfg", SimpleNamespace(pexels_api_key="key"))
    calls = []

    class Response:
        def __init__(self, query): self.query = query
        def raise_for_status(self): return None
        def json(self):
            place = "Krakow" if self.query.startswith("Gołanice") else "Poland landscape"
            return {"photos": [{"id": 1, "alt": place, "url": "https://pexels.test/poland",
                                "src": {"large": "https://img.test/poland.jpg"}}]}

    def fake_get(_url, **kwargs):
        query = kwargs["params"]["query"]; calls.append(query); return Response(query)

    monkeypatch.setattr(images.httpx, "get", fake_get)
    result = images.enrich({"title": "Project", "location": "Gołanice, Poland", "country_code": "PL"})
    assert calls == ["Gołanice Poland", "Poland travel landscape"]
    assert result["image_url"] == "https://img.test/poland.jpg"


def test_save_uploaded_normalises_and_persists(monkeypatch, tmp_path):
    monkeypatch.setattr(images, "cfg", SimpleNamespace(media_dir=str(tmp_path)))
    raw = BytesIO()
    Image.new("RGB", (2400, 1600), "red").save(raw, "PNG")
    url = images.save_uploaded(raw.getvalue())
    assert url.startswith("/media/opportunities/") and url.endswith(".jpg")
    saved = tmp_path / url.removeprefix("/media/")
    assert saved.is_file()
    with Image.open(saved) as result:
        assert result.format == "JPEG"
        assert result.width <= 1800
        assert result.height <= 1200
