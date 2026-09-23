import csv
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
STATIC = ROOT / "app" / "api" / "static"


def test_pwa_has_required_icons_and_root_service_worker():
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert (STATIC / "icon-192.png").stat().st_size > 1_000
    assert (STATIC / "icon-512.png").stat().st_size > 1_000
    assert 'navigator.serviceWorker.register("/sw.js")' in (
        STATIC / "discover-product.js"
    ).read_text(encoding="utf-8")
    service_worker = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert '"/guia"' in service_worker
    assert '"/assets/compatibility.js"' in service_worker


def test_home_has_compact_flow_and_mobile_navigation():
    html = (STATIC / "discover.html").read_text(encoding="utf-8")
    assert 'class="mobile-bottom-nav"' not in html
    assert 'class="nav-more"' in html
    assert 'class="mobile-symbol"' in html
    assert 'href="/organizaciones"' in html
    assert 'id="productMatches"' in html
    assert 'class="product-edit-btn"' in html
    assert 'id="installApp"' not in html
    assert 'class="wrap weekly-top"' not in html
    assert 'id="rowSoon"' in html
    assert 'id="rowYE"' in html
    assert 'id="rowTC"' in html
    assert 'id="rowESC"' in html
    assert '["rowESC",ecs]' in html
    assert 'href="/guia"' in html
    assert 'data-product-open="profile"' in html
    assert 'href="/world"' not in html
    assert "Mis solicitudes" not in html
    assert "Comparar oportunidades" not in html


def test_shared_compatibility_and_guide_are_available():
    compatibility = (STATIC / "compatibility.js").read_text(encoding="utf-8")
    guide = (STATIC / "guia.html").read_text(encoding="utf-8")
    assert "eligibility_country_codes" in compatibility
    assert "participant_min_age" in compatibility
    assert 'id:"nature"' in compatibility
    assert 'id:"facilitation"' in compatibility
    assert "missingRequired" in compatibility
    assert "matchedAvoid" in compatibility
    assert "extendedText" in compatibility
    assert "missingKeywords" in compatibility
    assert "infopack_enriched" in compatibility
    assert "Travel budget" in guide
    assert "No delegues tu candidatura a una IA" in guide
    assert "10–99 km" in guide


def test_world_is_not_linked_or_allowed_by_public_proxy():
    home = (STATIC / "discover.html").read_text(encoding="utf-8")
    caddy = (ROOT / "docker" / "Caddyfile").read_text(encoding="utf-8")
    assert "/world" not in home
    assert "@world_oculto" in caddy
    assert "/assets/world.html" in caddy


def test_compatibility_profile_only_persists_relevant_fields():
    script = (STATIC / "discover-product.js").read_text(encoding="utf-8")
    profile_block = script[script.index("function openProfile"):script.index("function addApplication")]
    assert "productAge" in profile_block
    assert "productResidence" in profile_block
    assert "productType" in profile_block
    assert "priorities:selected" in profile_block
    assert "pref-btn" in profile_block
    assert "Indiferente" in profile_block
    assert 'data-note="affinityNote"' in profile_block
    assert "productRequiredText" in profile_block
    assert "requiredText:" in profile_block
    assert "productLanguages" not in profile_block
    assert "productExperience" not in profile_block
    assert "productStrengths" not in profile_block


def test_secondary_pages_share_the_same_back_navigation():
    for name in ("guia.html", "organizaciones.html"):
        html = (STATIC / name).read_text(encoding="utf-8")
        assert 'href="/"' in html
        assert 'href="/mapa"' in html
        assert "Mi compatibilidad" not in html
    estadisticas = (STATIC / "estadisticas.html").read_text(encoding="utf-8")
    assert 'href="/"' in estadisticas
    assert 'href="/mapa"' in estadisticas


def test_detail_dialog_has_single_full_page_action():
    script = (STATIC / "discover-product.js").read_text(encoding="utf-8")
    detail_block = script[script.index("function enhanceDetail"):script.index("function updateFilterChips")]
    assert "detail-product-bar" not in detail_block
    assert 'data-product-open="profile"' not in detail_block
    assert "Abrir ficha completa" in detail_block
    assert "trace-note" in detail_block


def test_country_flags_cover_non_striped_designs():
    from app.publisher.opportunity_card import _flag
    from PIL import Image

    for code in ("TR", "GR", "SE", "FI", "DK", "NO", "IT", "ES", "ZZ"):
        canvas = Image.new("RGB", (140, 100), "#ffffff")
        _flag(canvas, 10, 10, 120, 80, code)  # must not raise for any of these


def test_catalog_and_map_can_sort_by_affinity():
    discover = (STATIC / "discover.html").read_text(encoding="utf-8")
    mapa = (STATIC / "mapa.html").read_text(encoding="utf-8")
    assert 'data-home-sort="affinity"' in discover
    assert "affinityRank" in discover
    assert 'order==="affinity"&&window.CorradiCompatibility' in discover
    assert 'data-sort="affinity"' in mapa
    assert "affinityRank" in mapa
    assert 'sortMode === "affinity"' in mapa


def test_ecs_duration_filter_is_contextual_in_catalog_and_map():
    discover = (STATIC / "discover.html").read_text(encoding="utf-8")
    mapa = (STATIC / "mapa.html").read_text(encoding="utf-8")
    assert 'id="ecsDuration"' in discover or 'select.id="ecsDuration"' in discover
    assert "durationMonths" in discover
    assert 'id="ecsMaxMonths"' in mapa
    assert 'id="ecsDurationFilter"' in mapa
    assert "state.ecsMaxMonths" in mapa
    assert 'var ecsSelected = state.types.has("VOLUNTEERING")' in mapa
    assert 'params.has("ecs_max")' in mapa
    assert 'params.set("ecs_max"' in discover
    assert 'types:Array.from(state.types)' in mapa


def test_map_starts_two_zoom_levels_closer():
    mapa = (STATIC / "mapa.html").read_text(encoding="utf-8")
    assert mapa.count('setView([48.6, 12], 5') == 3
    assert "bootingMap && !_p.get" in mapa


def test_sending_organisation_dataset_is_substantial():
    source = ROOT / "docs" / "asociaciones_erasmus_juventud_contactos.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 400
    assert all(row.get("nombre") and row.get("ciudad_provincia") for row in rows)
