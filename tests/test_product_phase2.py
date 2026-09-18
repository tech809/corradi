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
    assert 'class="mobile-bottom-nav"' in html
    assert 'href="/organizaciones"' in html
    assert 'id="installApp"' in html
    assert 'class="wrap section collections-section"' not in html
    assert 'class="wrap weekly-top"' not in html
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
    assert 'data-mode="required"' in profile_block
    assert 'data-mode="positive"' in profile_block
    assert 'data-mode="avoid"' in profile_block
    assert "productLanguages" not in profile_block
    assert "productExperience" not in profile_block
    assert "productStrengths" not in profile_block


def test_catalog_and_map_can_sort_by_affinity():
    discover = (STATIC / "discover.html").read_text(encoding="utf-8")
    mapa = (STATIC / "mapa.html").read_text(encoding="utf-8")
    assert 'data-home-sort="affinity"' in discover
    assert "affinityRank" in discover
    assert 'order==="affinity"&&window.CorradiCompatibility' in discover
    assert 'data-sort="affinity"' in mapa
    assert "affinityRank" in mapa
    assert 'sortMode === "affinity"' in mapa


def test_sending_organisation_dataset_is_substantial():
    source = ROOT / "docs" / "asociaciones_erasmus_juventud_contactos.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 400
    assert all(row.get("nombre") and row.get("ciudad_provincia") for row in rows)
