from datetime import date

from app.publisher import telegram_publisher as pub

OPP = {
    "identifier": "CORRADI-2026-0001",
    "title": "Green Roots",
    "type": "YOUTH_EXCHANGE",
    "topic": "sostenibilidad",
    "location": "Oviedo",
    "country_code": "ES",
    "start_date": date(2026, 9, 12),
    "end_date": date(2026, 9, 20),
    "application_deadline": date(2026, 8, 25),
    "deadline_estimated": False,
    "application_url": "https://forms.gle/x",
    "summary": "Intercambio sobre sostenibilidad.",
}


def test_format_opportunity_html():
    t = pub.format_opportunity(OPP)
    assert "Green Roots" in t
    assert "CORRADI-2026-0001" not in t  # el identificador ya no se muestra, es interno
    assert "2026-08-25" in t
    assert "Youth Exchange: sostenibilidad" in t
    assert "Oviedo" in t and "ES" not in t.split("📍")[1].split("\n")[0]  # sin código de país


def test_format_opportunity_whatsapp_bold():
    t = pub.format_opportunity_whatsapp(OPP)
    assert "*Green Roots*" in t
    assert "<b>" not in t  # WhatsApp no usa HTML
    assert "CORRADI-2026-0001" not in t


def test_daily_summary_empty():
    t = pub.format_daily_summary([], today=date(2026, 7, 21))
    assert "no hay" in t.lower()
    assert "21 de julio de 2026" in t


def test_daily_summary_list():
    t = pub.format_daily_summary([OPP], today=date(2026, 7, 21))
    assert "Green Roots" in t
    assert "21 de julio de 2026" in t
    assert "1 oportunidad abierta" in t
    assert "CORRADI-2026-0001" not in t
    assert "Fecha límite inscripción: 2026-08-25" in t
    assert "🎒 Youth Exchange (1)" in t  # agrupado por tipo


def test_daily_summary_groups_by_type():
    training = {**OPP, "identifier": "CORRADI-2026-0002", "title": "TC Test", "type": "TRAINING_COURSE"}
    ecs = {**OPP, "identifier": "CORRADI-2026-0003", "title": "ECS Test", "type": "VOLUNTEERING"}
    t = pub.format_daily_summary([OPP, training, ecs], today=date(2026, 7, 21))
    assert "🎒 Youth Exchange (1)" in t
    assert "🎓 Training Course (1)" in t
    assert "🤝 ECS (1)" in t
    assert t.index("Youth Exchange") < t.index("Training Course") < t.index("ECS")
