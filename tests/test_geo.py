from app import geo


def test_country_centroid():
    assert geo.country_centroid("ES") == (40.24, -3.65)
    assert geo.country_centroid("es") == (40.24, -3.65)
    assert geo.country_centroid(None) is None
    assert geo.country_centroid("ZZ") is None


def test_is_country_level():
    lat, lon = geo.COUNTRY_CENTROIDS["IT"]
    assert geo.is_country_level(lat, lon, "IT") is True
    # Una ciudad concreta (Turín) no es el centroide del país
    assert geo.is_country_level(45.07, 7.69, "IT") is False
    assert geo.is_country_level(None, None, "IT") is False
    assert geo.is_country_level(lat, lon, None) is False


def test_country_only_location_in_several_languages():
    assert geo.is_country_only_location("Spain", "ES") is True
    assert geo.is_country_only_location("Polonia", "PL") is True
    assert geo.is_country_only_location("Slovak Republic", "SK") is True
    assert geo.is_country_only_location("Islas Canarias, España", "ES") is False
    assert geo.is_country_only_location("Trakai, Lithuania", "LT") is False


def test_geocode_falls_back_to_country(monkeypatch):
    """Si Nominatim no encuentra la ciudad, se cae al centro del país en vez de quedarse sin pin."""
    monkeypatch.setattr(geo, "_nominatim", lambda *a, **k: None)
    assert geo.geocode("Un sitio que no existe", "PL") == geo.COUNTRY_CENTROIDS["PL"]


def test_geocode_without_location_uses_country(monkeypatch):
    monkeypatch.setattr(geo, "_nominatim", lambda *a, **k: None)
    assert geo.geocode(None, "GR") == geo.COUNTRY_CENTROIDS["GR"]
    assert geo.geocode("", "GR") == geo.COUNTRY_CENTROIDS["GR"]


def test_geocode_country_name_uses_centroid_without_network(monkeypatch):
    monkeypatch.setattr(
        geo, "_nominatim", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe usarse"))
    )
    assert geo.geocode("Spain", "ES") == geo.COUNTRY_CENTROIDS["ES"]


def test_geocode_returns_none_without_country(monkeypatch):
    monkeypatch.setattr(geo, "_nominatim", lambda *a, **k: None)
    monkeypatch.setattr(geo, "_nominatim_country", lambda *a, **k: None)
    assert geo.geocode("Sitio raro", None) is None


def test_geocode_country_outside_centroid_table(monkeypatch):
    """Un país que no está en COUNTRY_CENTROIDS (p.ej. Marruecos) no debe quedarse sin
    pin: se pregunta por el país a Nominatim antes de rendirse."""
    assert "MA" not in geo.COUNTRY_CENTROIDS
    monkeypatch.setattr(geo, "_nominatim", lambda *a, **k: None)
    monkeypatch.setattr(geo, "_nominatim_country", lambda cc: (31.79, -7.09) if cc == "MA" else None)
    assert geo.geocode("Un sitio", "MA") == (31.79, -7.09)


def test_geocode_known_country_skips_network(monkeypatch):
    """Si el país está en la tabla local no se hace ninguna llamada extra de red."""
    called = []
    monkeypatch.setattr(geo, "_nominatim", lambda *a, **k: None)
    monkeypatch.setattr(geo, "_nominatim_country", lambda cc: called.append(cc))
    assert geo.geocode("Sitio", "PL") == geo.COUNTRY_CENTROIDS["PL"]
    assert called == []


def test_geocode_prefers_city(monkeypatch):
    monkeypatch.setattr(geo, "_nominatim", lambda *a, **k: (45.07, 7.69))
    assert geo.geocode("Turín", "IT") == (45.07, 7.69)


def test_geocode_retries_with_shorter_query(monkeypatch):
    """'Manjirón, Sierra Norte de Madrid' falla entero pero funciona recortado al primer trozo."""
    calls = []

    def fake(query, cc):
        calls.append(query)
        return (40.85, -3.55) if query.startswith("Manjirón,") and "Sierra" not in query else None

    monkeypatch.setattr(geo, "_nominatim_city", lambda *a, **k: None)
    monkeypatch.setattr(geo, "_nominatim", fake)
    assert geo.geocode("Manjirón, Sierra Norte de Madrid", "ES") == (40.85, -3.55)
    assert len(calls) == 2


def test_geocode_city_country_uses_structured_city_search(monkeypatch):
    """Regresión: "Lugo, España" no debe resolverse como Calle Lugo en Madrid."""
    calls = []

    def fake_city(city, cc):
        calls.append((city, cc))
        return (43.0118, -7.5566)

    monkeypatch.setattr(geo, "_nominatim_city", fake_city)
    monkeypatch.setattr(
        geo, "_nominatim", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe usarse"))
    )

    assert geo.geocode("Lugo, España", "ES") == (43.0118, -7.5566)
    assert calls == [("Lugo", "ES")]
