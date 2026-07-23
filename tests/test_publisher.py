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
    assert "1 oportunidad con inscripción abierta" in t
    assert "Resumen diario de oportunidades abiertas" in t
    assert "CORRADI-2026-0001" not in t
    assert "Fecha límite: 2026-08-25" in t         # etiqueta corta
    assert "12-20 sept" in t                       # fecha compacta, mismo mes
    assert "🎒 Youth Exchange (1)" in t            # agrupado por tipo
    # En el resumen (agrupado) NO se repite el tipo por línea: solo la temática pelada.
    assert "🏷️ sostenibilidad" in t
    assert "Youth Exchange: sostenibilidad" not in t


def test_compact_dates():
    same = pub.format_summary_item({**OPP, "start_date": date(2026, 10, 5), "end_date": date(2026, 11, 15)})
    assert "5 oct - 15 nov" in same               # meses distintos
    cross = pub.format_summary_item({**OPP, "start_date": date(2026, 12, 28), "end_date": date(2027, 1, 5)})
    assert "28 dic - 5 ene" in cross              # distinto año, se sobreentiende
    # En /editarmisproyectos (show_type por defecto) sí se ve el tipo
    assert "Youth Exchange:" in pub.format_summary_item(OPP)


def test_deadline_estimada_labels():
    normal = {**OPP, "deadline_estimated": True, "raw_message": "Intercambio en Italia, plazas abiertas"}
    ultima = {**OPP, "deadline_estimated": True, "raw_message": "🚨 ÚLTIMA HORA: quedan 2 plazas"}
    assert "(estimada)" in pub.format_opportunity(normal)
    assert "(estimada: última hora)" in pub.format_opportunity(ultima)
    assert "(estimada: última hora)" in pub.format_summary_item(ultima)
    assert "(estimada)" not in pub.format_opportunity(OPP)  # deadline explícita, sin sufijo


def test_daily_summary_groups_by_type():
    training = {**OPP, "identifier": "CORRADI-2026-0002", "title": "TC Test", "type": "TRAINING_COURSE"}
    ecs = {**OPP, "identifier": "CORRADI-2026-0003", "title": "ECS Test", "type": "VOLUNTEERING"}
    t = pub.format_daily_summary([OPP, training, ecs], today=date(2026, 7, 21))
    assert "🎒 Youth Exchange (1)" in t
    assert "🎓 Training Course (1)" in t
    assert "🤝 ECS (1)" in t
    assert t.index("Youth Exchange") < t.index("Training Course") < t.index("ECS")
