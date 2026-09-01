import asyncio
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


def test_format_opportunity_whatsapp_incluye_bandera_y_categoria():
    """Sin foto (el canal de difusión de WhatsApp es solo texto), así que la bandera y la
    categoría -- que en Telegram van en la imagen del post, no en el pie -- tienen que
    escribirse aquí o se pierden por completo en la copia. Categoría y tema van en líneas
    separadas (no como antes, pegados con ' · ')."""
    t = pub.format_opportunity_whatsapp(OPP)
    lineas = t.split("\n")
    assert "🇪🇸 *Green Roots*" in lineas  # bandera de España, no el 🌍 genérico
    assert "🎒 Youth Exchange" in lineas  # categoría en su propia línea
    assert "🏷️ Temática: sostenibilidad" in lineas


def test_format_opportunity_whatsapp_categoria_sin_tema():
    """La categoría no puede depender de que haya `topic` -- sin tema, sigue apareciendo,
    y sin más, sin línea de Temática colgando."""
    sin_tema = {**OPP, "topic": None}
    t = pub.format_opportunity_whatsapp(sin_tema)
    assert "🎒 Youth Exchange" in t.split("\n")
    assert "Temática" not in t


def test_format_opportunity_whatsapp_bandera_generica_sin_pais():
    sin_pais = {**OPP, "country_code": None}
    t = pub.format_opportunity_whatsapp(sin_pais)
    assert "🌍 *Green Roots*" in t.split("\n")


def test_format_opportunity_whatsapp_cuenta_dias_para_el_limite():
    """La cuenta atrás depende de la fecha real de ejecución (_days_left no recibe `today`
    explícito aquí), así que solo se comprueba la forma, no el número exacto de días."""
    t = pub.format_opportunity_whatsapp(OPP)
    linea = next(l for l in t.split("\n") if l.startswith("⏳"))
    assert linea.startswith("⏳ Fecha límite: 2026-08-25")
    assert "*" not in linea  # sin negrita en el pie, a diferencia del título
    assert linea.strip().endswith(")") and "(" in linea  # "(quedan N días)" / "(cierra ...)"


def test_format_opportunity_whatsapp_incluye_resumen():
    t = pub.format_opportunity_whatsapp(OPP)
    assert "Intercambio sobre sostenibilidad." in t


def test_format_opportunity_whatsapp_sin_resumen_no_dejar_bloque_vacio():
    sin_resumen = {**OPP, "summary": None}
    t = pub.format_opportunity_whatsapp(sin_resumen)
    assert "\n\n\n" not in t


def test_format_opportunity_whatsapp_recorta_resumenes_largos():
    """Tope real en código (no solo en el prompt del extractor): unas ~3 líneas leídas en
    el móvil, calibrado contra un resumen real tomado como referencia (228 caracteres)."""
    largo = {**OPP, "summary": (
        "Oportunidad de curso de formación Erasmus+ en Rettenegg, Austria, para 8 "
        "participantes de 18 a 30 años. El curso se centra en el bienestar a través de la "
        "naturaleza, actividades al aire libre y aprendizaje no formal, buscando "
        "desarrollar la resiliencia y la conciencia emocional. La participación está "
        "totalmente financiada por Erasmus+."
    )}
    t = pub.format_opportunity_whatsapp(largo)
    assert len(largo["summary"]) > pub._SUMMARY_WHATSAPP_MAX_LEN  # el original SÍ se pasa
    assert "financiada por Erasmus+" not in t          # la 3ª frase queda fuera
    assert "para 8 participantes de 18 a 30 años." in t  # se queda con frases completas


def test_cap_summary_corta_en_frase_completa_aunque_sea_corta():
    """Bug real: exigir que el corte pasara de un % del límite producía un corte a mitad
    de palabra cuando la única frase completa disponible era corta pero perfectamente
    válida -- mejor una frase corta que media frase con puntos suspensivos."""
    texto = "Primera frase corta. " + "Segunda frase mucho más larga " * 15
    r = pub._cap_summary(texto, limit=50)
    assert r == "Primera frase corta."


def test_cap_summary_sin_puntos_corta_por_palabra():
    r = pub._cap_summary("x " * 200, limit=50)
    assert r.endswith("…")
    assert not r[:-1].endswith(" ")  # no dos espacios antes de la elipsis
    assert len(r) <= 51


def test_cap_summary_texto_corto_no_se_toca():
    assert pub._cap_summary("Resumen breve.") == "Resumen breve."


def test_format_opportunity_whatsapp_campos_de_contacto_solo_si_existen():
    """Cada campo (Infopack/Form/Contacto/Mapa) es una línea aparte y SOLO sale si hay
    dato -- nunca una línea vacía o "Infopack: -" para rellenar a mano."""
    completa = {
        **OPP,
        "infopack_url": "https://salto-youth.net/tools/toy/infopack.pdf",
        "application_url": "https://forms.gle/x",
        "contact_information": "info@ejemplo.eu",
    }
    t = pub.format_opportunity_whatsapp(completa)
    assert "Infopack: https://salto-youth.net/tools/toy/infopack.pdf" in t
    assert "Form: https://forms.gle/x" in t
    assert "Contacto: info@ejemplo.eu" in t
    assert "Mapa: https://mapa.proactivefuture.eu/2026-0001" in t

    solo_form = {**OPP, "infopack_url": None, "contact_information": None}
    t2 = pub.format_opportunity_whatsapp(solo_form)
    assert "Infopack:" not in t2
    assert "Form: https://forms.gle/x" in t2
    assert "Contacto:" not in t2
    assert "Mapa: https://mapa.proactivefuture.eu/2026-0001" in t2  # el mapa sale siempre que hay identifier


def test_format_opportunity_whatsapp_sin_ningun_contacto_ni_mapa():
    sin_nada = {k: v for k, v in OPP.items() if k not in ("identifier", "application_url")}
    t = pub.format_opportunity_whatsapp(sin_nada)
    assert "Infopack:" not in t and "Form:" not in t and "Contacto:" not in t and "Mapa:" not in t


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


def test_short_map_link():
    assert pub._short_map_link("CORRADI-2026-0040") == "https://mapa.proactivefuture.eu/2026-0040"
    assert pub._short_map_link(None) is None
    assert pub._short_map_link("algo-sin-prefijo") is None


def test_format_top_projects_for_telegram_and_whatsapp():
    opps = [{**OPP, "title": "Green & Digital", "location": "Lugo, España"}]
    telegram = pub.format_top_projects(opps, html=True)
    whatsapp = pub.format_top_projects(opps, html=False)
    assert "🔥 <b>TOP 3 DE LA SEMANA</b>" in telegram
    assert "Green &amp; Digital" in telegram
    assert '<a href="https://mapa.proactivefuture.eu/2026-0001">Ver proyecto</a>' in telegram
    assert "🔥 TOP 3 DE LA SEMANA" in whatsapp
    assert "Green & Digital" in whatsapp
    assert "https://mapa.proactivefuture.eu/2026-0001" in whatsapp
    assert "<b>" not in whatsapp and "<a " not in whatsapp


def test_weekly_topics_summary_groups_similar_themes_not_type():
    """'sostenibilidad' y 'cambio climático, medio ambiente' son temas distintos en texto
    literal y en tipo (YOUTH_EXCHANGE vs VOLUNTEERING) pero deben caer en el MISMO grupo
    temático (medioambiente y sostenibilidad)."""
    eco = {**OPP, "identifier": "CORRADI-2026-0003", "title": "Eco Test",
           "type": "VOLUNTEERING", "topic": "cambio climático, medio ambiente", "telegram_message_id": 42}
    t = pub.format_weekly_topics_summary([OPP, eco])
    assert "Medioambiente y sostenibilidad (2)" in t
    assert "• Green Roots" in t
    assert '<a href="https://t.me/erasmuscorradi/42">Eco Test</a>' in t  # solo enlaza si hay message_id


def test_classify_topic_uses_only_primary_tag():
    """El prompt del extractor pide el topic ordenado por importancia (principal primero);
    la clasificación debe fiarse SOLO de esa primera etiqueta, no de las secundarias, para
    no diluir la agrupación con temas que solo aparecen de forma tangencial."""
    # Secundaria "arte" pertenece a otro tema, pero la principal manda.
    assert pub._classify_topic("sostenibilidad, arte, storytelling") == "🌱 Medioambiente y sostenibilidad"
    # Si la principal no encaja en ningún tema conocido, no se rescata mirando las demás.
    assert pub._classify_topic("un tema muy raro, sostenibilidad") == pub._OTRAS_TEMA


def test_classify_topic_word_boundary_avoids_false_positive():
    """Bug real: la keyword 'art' (para 'arte') hacía match como substring suelto dentro de
    'partnership building', clasificando mal 'Waves of Cooperation' (proyectos) como Arte."""
    assert pub._classify_topic("partnership building") != "🎨 Arte, narrativa y creatividad"
    assert pub._classify_topic("partnership building") == "📋 Gestión de proyectos y educación no formal"
    assert pub._classify_topic("art, creatividad") == "🎨 Arte, narrativa y creatividad"  # sigue cazando "arte" de verdad


def test_weekly_topics_summary_merges_singleton_theme_into_otras():
    """Un tema con una sola ficha coincidente (aquí 'derechos humanos', ningún otro tema
    encaja) no debe salir como grupo suelto de 1 — se funde en Otras temáticas."""
    unique = {**OPP, "title": "DDHH Test", "topic": "derechos humanos"}
    t = pub.format_weekly_topics_summary([unique])
    assert "Justicia social y derechos humanos" not in t
    assert "Otras temáticas (1)" in t
    assert "DDHH Test" in t


def test_weekly_topics_summary_caps_long_group():
    many = [
        {**OPP, "identifier": f"CORRADI-2026-{i:04d}", "title": f"Op {i}", "topic": f"tema{i}"}
        for i in range(25)
    ]
    t = pub.format_weekly_topics_summary(many, max_per_group=20)
    assert "Otras temáticas (25)" in t  # ninguno coincide con ningún tema conocido
    assert "+5 más en este grupo" in t
    assert "+5 más en este grupo" in t


def test_weekly_topics_summary_empty():
    t = pub.format_weekly_topics_summary([])
    assert "no hay ninguna" in t.lower()


def test_weekly_topics_summary_blank_line_between_groups():
    eco = {**OPP, "identifier": "CORRADI-2026-0003", "title": "Eco Test", "topic": "sostenibilidad"}
    arte = {**OPP, "identifier": "CORRADI-2026-0004", "title": "Arte Test", "topic": "arte, creatividad"}
    t = pub.format_weekly_topics_summary([OPP, eco, arte])
    assert "\n\n<b>🎨 Arte" in t or "\n\n<b>🌱 Medioambiente" in t  # línea en blanco antes del 2º grupo


def test_week_range_label_same_and_different_month():
    assert pub._week_range_label(date(2026, 7, 20), date(2026, 7, 25)) == "20 - 25 de julio"
    assert pub._week_range_label(date(2026, 7, 27), date(2026, 8, 2)) == "27 jul - 2 de agosto"


def test_format_weekly_full_summary_combines_stats_and_themes():
    eco = {**OPP, "identifier": "CORRADI-2026-0003", "title": "Eco Test", "topic": "sostenibilidad"}
    another_eco = {**OPP, "identifier": "CORRADI-2026-0004", "title": "Eco Test 2", "topic": "medio ambiente"}
    t = pub.format_weekly_full_summary(
        26,
        [{"country_code": "ES", "n": 7}], [{"type": "YOUTH_EXCHANGE", "n": 19}],
        date(2026, 7, 20), date(2026, 7, 25),
        [eco, another_eco],
    )
    assert "RESUMEN SEMANAL · 20 - 25 de julio" in t
    assert "publicadas esta semana" not in t  # se quitó a petición del usuario
    assert "26 abiertas ahora mismo. Los domingos te las recordamos todas agrupadas por TEMÁTICA:" in t
    assert "🇪🇸 España (7)" in t
    assert "Los domingos te las recordamos todas agrupadas por TEMÁTICA:" in t
    assert "Medioambiente y sostenibilidad (2)" in t
    assert "Eco Test" in t and "Eco Test 2" in t


def test_send_chunked_dm_splits_long_text_on_line_boundaries(monkeypatch):
    """Bug real encontrado probando el scraper de SALTO-YOUTH en producción: una
    descripción larga superaba el límite de 4096 caracteres de Telegram y tumbaba el envío
    entero (`BadRequest: Message is too long`)."""
    sent = []

    async def fake_notify(admin_id, text):
        sent.append(text)

    monkeypatch.setattr(pub, "notify_admin", fake_notify)

    long_text = "\n".join(f"Línea {i} " + "x" * 80 for i in range(100))
    asyncio.run(pub.send_chunked_dm(1, long_text))

    assert len(sent) > 1
    assert all(len(chunk) <= pub._DM_MAX_LEN for chunk in sent)
    assert "\n".join(sent) == long_text  # nada se pierde ni se corta a mitad de línea


def test_send_chunked_dm_single_message_when_short(monkeypatch):
    sent = []

    async def fake_notify(admin_id, text):
        sent.append(text)

    monkeypatch.setattr(pub, "notify_admin", fake_notify)
    asyncio.run(pub.send_chunked_dm(1, "corto"))
    assert sent == ["corto"]


def test_opportunity_keyboard_no_map_button_infopack_first():
    both = {**OPP, "infopack_url": "https://drive.example/info.pdf"}
    kb = pub.opportunity_keyboard(both)
    labels = [btn.text for btn in kb.inline_keyboard[0]]
    assert labels == ["📄 Infopack", "👉 Formulario"]
    assert not any("Mapa" in label for label in labels)


def test_opportunity_keyboard_only_form():
    kb = pub.opportunity_keyboard(OPP)  # OPP solo trae application_url
    labels = [btn.text for btn in kb.inline_keyboard[0]]
    assert labels == ["👉 Formulario"]


def test_opportunity_keyboard_none_when_no_links():
    no_links = {**OPP, "application_url": None}
    assert pub.opportunity_keyboard(no_links) is None
