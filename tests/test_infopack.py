import httpx

from app.llm import infopack


_RealClient = httpx.Client


def _client_factory(handler):
    def factory(*, follow_redirects, timeout):
        return _RealClient(transport=httpx.MockTransport(handler), follow_redirects=follow_redirects, timeout=timeout)
    return factory


def test_downloadable_url_rewrites_drive_share_link():
    url = "https://drive.google.com/file/d/ABC123/view?usp=sharing"
    assert infopack._downloadable_url(url) == "https://drive.google.com/uc?export=download&id=ABC123"


def test_downloadable_url_leaves_other_hosts_untouched():
    url = "https://example.com/doc.pdf"
    assert infopack._downloadable_url(url) == url


def test_read_rewrites_drive_link_reached_via_a_redirect(monkeypatch):
    # Un acortador (tr.ee, tinyurl...) puede redirigir a un enlace compartido de Drive:
    # si no reescribimos ESE salto también, se descarga el visor HTML en vez del PDF.
    def handler(request):
        if request.url.host == "tr.ee":
            return httpx.Response(302, headers={"location": "https://drive.google.com/file/d/XYZ789/view"})
        if request.url.host == "drive.google.com" and request.url.path == "/uc":
            assert dict(request.url.params) == {"export": "download", "id": "XYZ789"}
            return httpx.Response(200, content=b"x" * 200, headers={"content-type": "text/plain"})
        raise AssertionError(f"unexpected request to {request.url}")

    monkeypatch.setattr(infopack, "_public_url", lambda url: True)
    monkeypatch.setattr(infopack.httpx, "Client", _client_factory(handler))
    text = infopack.read("https://tr.ee/whatever")
    assert text == "x" * 200


def test_read_returns_none_when_extracted_text_too_short(monkeypatch):
    def handler(request):
        return httpx.Response(200, content=b"short", headers={"content-type": "text/plain"})

    monkeypatch.setattr(infopack, "_public_url", lambda url: True)
    monkeypatch.setattr(infopack.httpx, "Client", _client_factory(handler))
    assert infopack.read("https://example.com/doc.txt") is None


def test_read_gives_up_after_too_many_redirects(monkeypatch):
    def handler(request):
        return httpx.Response(302, headers={"location": "https://example.com/next"})

    monkeypatch.setattr(infopack, "_public_url", lambda url: True)
    monkeypatch.setattr(infopack.httpx, "Client", _client_factory(handler))
    assert infopack.read("https://example.com/start") is None
