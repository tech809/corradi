"""Calidad de datos del catálogo: deadlines estimadas, títulos, temáticas, resúmenes y
detección de última hora."""
from datetime import date, datetime, timezone

import pytest

from app.domain.project import (
    cap_estimated_deadline, cap_summary, clean_title, clean_topic, is_last_minute, normalize,
    smart_title_case, strip_summary_boilerplate,
)
from app.scheduler.backfill_data_quality import compute_changes
from app.sources import european_youth_portal as eyp


# --- 1. Deadline estimada vs inicio ----------------------------------------------------

def test_estimated_deadline_capped_before_start():
    # Caso real CORRADI-2026-1020: enviado el 04-11, empieza el 07-11, estimada 09-11.
    f = normalize({"start_date": "07/11/2026"}, date(2026, 11, 4), 5)
    assert f["deadline_estimated"] is True
    assert f["application_deadline"] == date(2026, 11, 6)


def test_estimated_deadline_never_before_today():
    f = normalize({"start_date": "05/11/2026"}, date(2026, 11, 4), 5)
    assert f["application_deadline"] == date(2026, 11, 4)
    f = normalize({"start_date": "04/11/2026"}, date(2026, 11, 4), 5)
    assert f["application_deadline"] == date(2026, 11, 4)


def test_estimated_deadline_untouched_when_start_far_or_unknown():
    assert normalize({"start_date": "01/12/2026"}, date(2026, 11, 4), 5)["application_deadline"] == date(2026, 11, 9)
    assert normalize({}, date(2026, 11, 4), 5)["application_deadline"] == date(2026, 11, 9)


def test_stated_deadline_is_not_capped():
    f = normalize({"start_date": "07/11/2026", "application_deadline": "10/11/2026"}, date(2026, 11, 4), 5)
    assert f["deadline_estimated"] is False
    assert f["application_deadline"] == date(2026, 11, 10)


def test_last_minute_estimate_also_capped():
    f = normalize({"start_date": "05/11/2026"}, date(2026, 11, 3), 5,
                  raw_text="ÚLTIMA HORA: plaza libre", last_minute_deadline_days=2)
    assert f["application_deadline"] == date(2026, 11, 4)


def test_cap_estimated_deadline_helper():
    today = date(2026, 11, 4)
    assert cap_estimated_deadline(date(2026, 11, 9), date(2026, 11, 7), today) == date(2026, 11, 6)
    assert cap_estimated_deadline(date(2026, 11, 9), None, today) == date(2026, 11, 9)
    assert cap_estimated_deadline(date(2026, 11, 9), date(2026, 11, 1), today) == today


# --- 2. Resúmenes ------------------------------------------------------------------------

def test_cap_summary_short_text_untouched():
    assert cap_summary("Breve.") == "Breve."
    assert cap_summary(None) is None


def test_cap_summary_cuts_at_sentence_boundary():
    text = ("A" * 300) + ". " + ("Segunda frase que no cabe entera " * 10) + "."
    out = cap_summary(text, 500)
    assert out == ("A" * 300) + "."


def test_cap_summary_falls_back_to_word_with_ellipsis():
    text = "palabra " * 100
    out = cap_summary(text, 50)
    assert out.endswith("…")
    assert len(out) <= 51
    assert out[:-1].split()[-1] == "palabra"


def test_cap_summary_ignores_too_early_sentence_end():
    # Un punto en los primeros 40 % no debe dejar un resumen ridículamente corto.
    text = "Hola. " + "texto largo sin puntos " * 40
    out = cap_summary(text, 500)
    assert len(out) > 400 and out.endswith("…")


def test_cap_summary_line_boundary_gets_ellipsis():
    text = ("x" * 300) + "\nTareas:\n• " + ("y " * 200)
    out = cap_summary(text, 500)
    assert out == ("x" * 300) + "…"   # sin el encabezado "Tareas:" colgando


def test_strip_boilerplate():
    assert strip_summary_boilerplate("See full description and how to apply on our website, here.") is None
    assert strip_summary_boilerplate(
        "Great project in Italy. Read more: https://example.org/x"
    ) == "Great project in Italy."
    keep = "Volunteers will see the full impact of their work."
    assert strip_summary_boilerplate(keep) == keep


# --- 3. Temáticas ------------------------------------------------------------------------

def test_clean_topic_drops_numeric_codes():
    assert clean_topic("retos sociales, 253") == "retos sociales"
    assert clean_topic("235, 259") is None
    assert clean_topic("deporte, deporte, 2") == "deporte"
    assert clean_topic(None) is None


def test_eyp_topics_prefer_named_codes():
    row = {"topics": ["socl", "235", "edu", "253"], "esc_topics": ["socl", "edu"]}
    assert eyp.topic_labels(row) == "retos sociales, educación y formación"
    assert eyp.topic_labels({"topics": ["235", "sprt"]}) == "deporte"
    assert eyp.topic_labels({"topics": ["235"]}) is None


# --- 4. Títulos --------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("ESC IN ERZURUM/TURKIYE", "ESC in Erzurum/Turkiye"),
    ("MENS SANA IN CORPORE SANO PRO", "Mens Sana in Corpore Sano Pro"),
    ("AYUNTAMIENTO DE RIBADAVIA (SUPPORT THE LOCAL COMMUNITY)",
     "Ayuntamiento de Ribadavia (Support the Local Community)"),
    ("YOU(TH) 4 FUTURE", "You(th) 4 Future"),
    ("COMIC4EU", "Comic4EU"),
    ("VOICES OF SOLIDARITY II", "Voices of Solidarity II"),
    ("ESC VOLUNTEERING IN A NURSERY AND A WOMEN’S COMMUNITY HOUSE",
     "ESC Volunteering in a Nursery and a Women’s Community House"),
    ("SOCIO-EDUCATIONAL CENTER FOR CHILDREN - VOLUNTEERING IN ITALY",
     "Socio-Educational Center for Children - Volunteering in Italy"),
    ("“COUNT ME IN!” 3.0", "“Count Me In!” 3.0"),
])
def test_shouting_titles_are_title_cased(raw, expected):
    assert clean_title(raw) == expected


@pytest.mark.parametrize("raw", [
    "You FuTuRe (30 DAYS TEAM VOLUNTEERING)",   # mayúsculas mezcladas a propósito
    "Help Desk YOUth",
    "Intercambio juvenil en Grecia",
    "ESC",                                        # demasiado corto para decidir
])
def test_non_shouting_titles_untouched(raw):
    assert clean_title(raw) == raw


def test_project_code_title_falls_back_to_organiser_and_town():
    out = clean_title("2026-1-TR01-ESC51-VTJ-000400833",
                      organiser="GENC GIRISIM EGITIM VE GENCLIK DERNEGI", town="ANKARA",
                      fallback_prefix="Voluntariado ESC")
    assert out == "Voluntariado ESC con Genc Girisim Egitim Ve Genclik Dernegi en Ankara"


def test_project_code_prefix_is_stripped():
    assert clean_title("2024-1-TR01-ESC51-VTJ-000200773 ENGELLİLERE GÖNÜLLÜ DESTEK (5)") == \
        "Engellilere Gönüllü Destek (5)"


def test_project_code_without_any_fallback_uses_default_or_keeps():
    assert clean_title("2026-1-TR01-ESC51-VTJ-000400833", default="X") == "X"
    assert clean_title("2026-1-TR01-ESC51-VTJ-000400833") == "2026-1-TR01-ESC51-VTJ-000400833"


def test_smart_title_case_keeps_vowelless_acronyms():
    assert smart_title_case("PROJECT WITH VTJ") == "Project with VTJ"


def test_normalize_cleans_title_and_topic():
    f = normalize({"title": "ART FOR INCLUSION", "topic": "arte, 235"}, date(2026, 1, 1), 5)
    assert f["title"] == "Art for Inclusion"
    assert f["topic"] == "arte"
    f = normalize({"title": "2025-1-ES02-KA152-YOU-000123456", "type": "YOUTH_EXCHANGE",
                   "organiser_name": "Asociación X"}, date(2026, 1, 1), 5)
    assert f["title"] == "Intercambio juvenil con Asociación X"


# --- EYP to_project ----------------------------------------------------------------------

def _eyp_row(**over):
    row = {
        "id": 1, "title": "2026-1-TR01-ESC51-VTJ-000400833", "organisation_name": "GENC GIRISIM",
        "town": "ANKARA", "country": "TR", "description": "<p>" + ("Frase de prueba. " * 60) + "</p>",
        "topics": ["socl", "235"], "esc_topics": ["socl"],
        "date_application_end": "2026-12-01T00:00:00Z", "date_start": "2027-01-10T00:00:00Z",
        "date_end": "2027-03-10T00:00:00Z", "volunteer_countries": ["ES"],
        "funding_programme": {"is_volunteering": True},
    }
    row.update(over)
    return row


def test_eyp_to_project_quality():
    p = eyp.to_project(_eyp_row(), datetime(2026, 11, 6, tzinfo=timezone.utc))
    assert p["title"] == "Voluntariado ESC con Genc Girisim en Ankara"
    assert p["topic"] == "retos sociales"
    assert len(p["summary"]) <= 500 and p["summary"].endswith(".")
    assert p["covered_costs"] == eyp.ESC_VOLUNTEERING_COVERED_COSTS
    # La descripción completa no se recorta.
    assert len(p["detailed_description"]) > 500


def test_eyp_title_dashes_are_not_turned_into_list():
    p = eyp.to_project(_eyp_row(title="Help Desk YOUth - October - November 2026"),
                       datetime(2026, 11, 6, tzinfo=timezone.utc))
    assert p["title"] == "Help Desk YOUth - October - November 2026"


# --- 5. Última hora ----------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "¡ÚLTIMA HORA! Quedan plazas para Italia",
    "ultima hora: intercambio en Rumanía",
    "Plazas de última hora para Turquía",
    "Últimas plazas disponibles",
    "ultimas plazas",
    "Queda una plaza libre para el TC en Polonia",
    "Plaza libre en intercambio juvenil",
    "Solo quedan 2 plazas",
    "Se busca sustituto/a para un intercambio en Grecia",
    "Buscamos una sustituta para el proyecto",
    "Necesitamos a alguien como sustituto",
    "Llamamiento urgente: intercambio en Lituania",
    "Convocatoria urgente para un training course",
    "URGENTE intercambio en Portugal",
    "🚨 Urgente: 1 plaza",
    "¡Urgente! Salimos el lunes",
    "Se busca urgentemente participante",
    "Empieza en 3 días, ¡apúntate!",
    "El proyecto comienza la semana que viene",
    "Last minute opportunity in Poland",
    "LAST-MINUTE OPPORTUNITY - Activities for children",
    "LAST CALL: ESC volunteering with migrants",
    "Last chance to join our youth exchange",
    "Only 2 places left!",
    "We are looking for a replacement participant",
    "Replacement needed for the TC in Latvia",
    "Apply ASAP",
    "The project starts in a few days",
    "Starting in 5 days in Riga",
    "We urgently need one volunteer",
    "URGENT: youth exchange in Italy",
])
def test_is_last_minute_positive(text):
    assert is_last_minute(text), text


@pytest.mark.parametrize("text", [
    None,
    "",
    "Intercambio juvenil en Grecia, plazas abiertas",
    "Hay 30 plazas libres para participantes de 18 a 25 años",
    "El último día del proyecto haremos una fiesta",
    "Last year we hosted 20 volunteers",
    "On the last day there is an evaluation",
    "Ayuda humanitaria urgente para comunidades afectadas",   # urgente en una frase normal
    "Responder a necesidades urgentes de la población",
    "Grupo insurgente y detergente",                          # 'urgente' dentro de palabras
    "Urgencias del hospital",
    "Research on hip replacement therapies",
    "Desarrollar un sustituto del plástico",
    "The urgent needs of refugees in the region",
    "Activities include last-mile delivery training",
    "Visitamos el Museo de la Última Cena",
    "The volunteering starts in September",
    "Starts on 12 days of action",
])
def test_is_last_minute_negative(text):
    assert not is_last_minute(text), text


# --- 7. Backfill (lógica pura, sin BD) ---------------------------------------------------

def test_backfill_compute_changes():
    today = date(2026, 11, 6)
    row = {
        "identifier": "CORRADI-2026-1020", "source": None, "title": "ART FOR INCLUSION",
        "topic": "arte, 235", "summary": "x", "detailed_description": None,
        "organiser_name": "x", "location": "Ankara, TR", "type": "YOUTH_EXCHANGE",
        "deadline_estimated": True, "start_date": date(2026, 11, 9),
        "application_deadline": date(2026, 11, 12),
    }
    ch = compute_changes(row, today)
    assert ch == {"title": "Art for Inclusion", "topic": "arte",
                  "application_deadline": date(2026, 11, 8)}


def test_backfill_eyp_summary_and_title():
    today = date(2026, 11, 6)
    long_desc = "Frase de prueba. " * 60
    row = {
        "identifier": "CORRADI-2026-0332", "source": "eyp",
        "title": "2026-1-TR01-ESC51-VTJ-000400833", "topic": "253",
        "summary": long_desc[:500], "detailed_description": long_desc,
        "organiser_name": "GENC GIRISIM", "location": "ANKARA, TR", "type": "VOLUNTEERING",
        "deadline_estimated": False, "start_date": date(2027, 1, 1),
        "application_deadline": date(2026, 12, 1),
    }
    ch = compute_changes(row, today)
    assert ch["title"] == "Voluntariado ESC con Genc Girisim en Ankara"
    assert ch["topic"] is None
    assert ch["summary"].endswith(".") and len(ch["summary"]) <= 500
    assert "application_deadline" not in ch


def test_backfill_noop_for_clean_row():
    row = {
        "identifier": "X", "source": None, "title": "Intercambio en Grecia", "topic": "arte",
        "summary": "Hola.", "detailed_description": None, "organiser_name": None,
        "location": None, "type": None, "deadline_estimated": True,
        "start_date": date(2026, 12, 1), "application_deadline": date(2026, 11, 10),
    }
    assert compute_changes(row, date(2026, 11, 6)) == {}
