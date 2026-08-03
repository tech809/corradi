"""Formatea y publica oportunidades en Telegram y prepara el handoff a WhatsApp."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import cfg
from app.domain.project import is_last_minute

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Nombres en español para los hashtags de país (destinos habituales de Erasmus+/CES).
# Si el país no está aquí, se usa el propio country_code como hashtag (p.ej. #DE).
_PAISES_ES = {
    "ES": "España", "PT": "Portugal", "FR": "Francia", "IT": "Italia", "DE": "Alemania",
    "AT": "Austria", "BE": "Bélgica", "NL": "PaísesBajos", "LU": "Luxemburgo", "IE": "Irlanda",
    "PL": "Polonia", "CZ": "Chequia", "SK": "Eslovaquia", "HU": "Hungría", "RO": "Rumanía",
    "BG": "Bulgaria", "GR": "Grecia", "HR": "Croacia", "SI": "Eslovenia", "EE": "Estonia",
    "LV": "Letonia", "LT": "Lituania", "FI": "Finlandia", "SE": "Suecia", "DK": "Dinamarca",
    "NO": "Noruega", "IS": "Islandia", "MT": "Malta", "CY": "Chipre", "TR": "Turquía",
    "RS": "Serbia", "MK": "MacedoniaDelNorte", "ME": "Montenegro", "BA": "BosniaYHerzegovina",
    "AL": "Albania", "XK": "Kosovo", "GE": "Georgia", "AM": "Armenia", "UA": "Ucrania",
    "MD": "Moldavia",
}

_TIPOS_ES = {
    "YOUTH_EXCHANGE": "Intercambio juvenil",
    "TRAINING_COURSE": "Training course",
    "VOLUNTEERING": "Voluntariado",
}

# Etiqueta que sustituye a "Temática" en la línea 🏷️ de cada oportunidad.
_TIPO_LABEL_TEMA = {
    "YOUTH_EXCHANGE": "Youth Exchange",
    "TRAINING_COURSE": "Training Course",
    "VOLUNTEERING": "ECS",
}

# Orden y cabecera visual de los grupos del resumen diario.
_GRUPOS_RESUMEN = [
    ("YOUTH_EXCHANGE", "🎒 Youth Exchange"),
    ("TRAINING_COURSE", "🎓 Training Course"),
    ("VOLUNTEERING", "🤝 ECS"),
]

# Taxonomía para el resumen semanal de temáticas: el `topic` que manda el extractor es
# texto libre (varias etiquetas por ficha, casi nunca coincide literal entre dos fichas —
# comprobado con datos reales: 29 topics únicos para 29 fichas), así que agrupar por texto
# exacto no agrupa nada. En su lugar, cada ficha se asigna al tema con más palabras clave
# coincidentes (basada en los topics reales vistos en producción; empate → el primero de
# la lista). Sin acentos y en minúsculas, comparado contra `_strip_accents(topic.lower())`.
_TEMAS = [
    ("🌱 Medioambiente y sostenibilidad",
     ["sostenib", "medio ambiente", "ecolog", "cambio climatic", "clima", "naturaleza",
      "economia circular", "agua", "green"]),
    ("🤝 Inclusión y diversidad",
     ["inclusi", "diversidad", "discapacidad", "igualdad", "equidad"]),
    ("🌍 Interculturalidad y participación juvenil",
     ["intercultural", "participacion juvenil", "youth exchange", "international", "ciudadania"]),
    ("🌟 Desarrollo personal y liderazgo",
     ["desarrollo personal", "liderazgo", "autoconocimiento", "inteligencia emocional",
      "asertividad", "bienestar", "well-being", "valores", "confianza"]),
    ("💻 Digital, IA y pensamiento crítico",
     ["digital", "inteligencia artificial", "artificial intelligence", "fake news",
      "critical thinking", "pensamiento critico", "tecnolog", "ai literacy"]),
    ("🎨 Arte, narrativa y creatividad",
     ["arte", "art", "storytelling", "narrac", "narrativ", "cine", "creativ", "teatro"]),
    ("📋 Gestión de proyectos y educación no formal",
     ["gestion de proyectos", "project management", "non-formal", "no formal",
      "proposal writing", "partnership", "diseno de proyectos", "gamification", "facilitation"]),
    ("⚖️ Justicia social y derechos humanos",
     ["justicia social", "derechos humanos", "colonialismo", "memoria", "activismo", "paz"]),
]
_OTRAS_TEMA = "📌 Otras temáticas"


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _classify_topic(topic: str | None) -> str:
    """Clasifica SOLO por la etiqueta principal (la primera del `topic`, coma-separado) —
    el prompt del extractor (`app/llm/prompts.py`) ya pide que venga ordenado por
    importancia, así que la primera es la temática central de la oportunidad; las
    secundarias no se usan aquí para no diluir la agrupación. `_OTRAS_TEMA` si la principal
    no encaja en ningún tema conocido de `_TEMAS`.

    Las palabras clave se buscan con límite de palabra a la izquierda (no substring suelto):
    un bug real lo encontró — la keyword "art" (para cazar "arte"/"artístico") hacía match
    dentro de "partnership building", clasificando mal "Waves of Cooperation" como Arte."""
    primary = (topic or "").split(",")[0].strip()
    t = _strip_accents(primary.lower())
    for label, keywords in _TEMAS:
        if any(re.search(r"\b" + re.escape(kw), t) for kw in keywords):
            return label
    return _OTRAS_TEMA


def _topic_label(o: dict[str, Any]) -> str:
    return _TIPO_LABEL_TEMA.get(o.get("type"), "Temática")


def _flag(country_code: str | None) -> str:
    """Emoji de bandera a partir de un código ISO 3166-1 alpha-2 (p.ej. 'DE' -> 🇩🇪)."""
    if not country_code or len(country_code) != 2 or not country_code.isalpha():
        return ""
    cc = country_code.upper()
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in cc)


def _days_left(deadline: str | date, today: date | None = None) -> str:
    """'quedan N días' / 'cierra mañana' / 'cierra hoy', a partir de la fecha límite (str
    ISO o date — según el caller, viene de la BD como date o ya serializada como str)."""
    today = today or date.today()
    if isinstance(deadline, str):
        y, m, d = (int(x) for x in deadline.split("-"))
        deadline = date(y, m, d)
    delta = (deadline - today).days
    if delta <= 0:
        return "cierra hoy"
    if delta == 1:
        return "cierra mañana"
    return f"quedan {delta} días"


def _valid_url(u: str | None) -> bool:
    """True solo si es una URL http(s) con pinta razonable. Usarlo SIEMPRE antes de meter
    un valor extraído por el LLM en un botón: Telegram rechaza la publicación ENTERA si la
    URL no es válida ("Button_url_invalid", visto en producción — el extractor puso un
    email en `application_url` en vez de un enlace real, y tumbó la publicación)."""
    return bool(u) and bool(re.fullmatch(r"https?://\S+", u.strip(), re.I))


def opportunity_keyboard(o: dict[str, Any]) -> InlineKeyboardMarkup | None:
    """Botones para el post del canal: formulario, infopack y "Ver en el mapa" (solo si hay
    MAP_PUBLIC_URL configurada), todos en UNA fila (como columnas). Cada oportunidad trae
    los campos que trae, así que salen solo los botones que aplican — nunca uno vacío.

    Formulario/Infopack solo se convierten en botón si `_valid_url()` los aprueba — si no
    (el LLM a veces mete un email o texto suelto en vez de una URL real), se quedan como
    texto en el pie (ver `format_opportunity`) en vez de tumbar la publicación entera.

    El contacto NUNCA es un botón, a propósito — siempre se queda como texto en el pie
    (ver `format_opportunity`). Motivo: Telegram rechaza botones `tel:` ("wrong port number
    specified in the url", visto en producción — un coordinador con
    contact_information="653743157, correo@x.com" hizo fallar la publicación entera). En
    vez de mantener una detección frágil de qué formatos de contacto son "seguros" para
    botón, más simple y sin ese riesgo: contacto siempre texto, punto.

    Sin botón de mapa (quitado a petición del usuario, 2026-07-25) — solo Infopack y
    Formulario, en ese orden (infopack primero si hay los dos)."""
    row = []
    if _valid_url(o.get("infopack_url")):
        row.append(InlineKeyboardButton("📄 Infopack", url=o["infopack_url"]))
    if _valid_url(o.get("application_url")):
        row.append(InlineKeyboardButton("👉 Formulario", url=o["application_url"]))
    return InlineKeyboardMarkup([row]) if row else None


def _est(o: dict[str, Any]) -> str:
    """Sufijo de la fecha límite cuando la hemos estimado nosotros (no venía en el mensaje).

    Se distingue el caso de última hora / últimas plazas releyendo el mensaje original
    (mismo criterio que usó `normalize` para acortar el margen a 2 días)."""
    if not o.get("deadline_estimated"):
        return ""
    return " (estimada: última hora)" if is_last_minute(o.get("raw_message")) else " (estimada)"


def _dates(o: dict[str, Any]) -> str:
    s, e = o.get("start_date"), o.get("end_date")
    if s and e:
        return f"{s} → {e}"
    return str(s or e or "fechas por confirmar")


# Abreviaturas de mes en español (RAE): sept. es la de septiembre, no "sep".
_MES_ABBR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]


def _compact_dates(o: dict[str, Any]) -> str:
    """Fechas de realización compactas, ignorando el año (se sobreentiende):
    mismo mes -> "5-15 sept"; meses distintos -> "5 oct - 15 nov"; distinto año -> "28 dic - 5 ene"."""
    def parse(v):
        p = str(v).split("-")
        return int(p[0]), int(p[1]), int(p[2])   # (año, mes, día)

    s, e = o.get("start_date"), o.get("end_date")
    if s and e:
        ys, ms, ds = parse(s)
        ye, me, de = parse(e)
        if ms == me and ys == ye:
            return f"{ds}-{de} {_MES_ABBR[ms - 1]}"
        return f"{ds} {_MES_ABBR[ms - 1]} - {de} {_MES_ABBR[me - 1]}"
    one = s or e
    if one:
        _, m, d = parse(one)
        return f"{d} {_MES_ABBR[m - 1]}"
    return "fechas por confirmar"


def _place(o: dict[str, Any]) -> str:
    """Ubicación, simplificada a como máximo "Ciudad/Región, País": una localización con
    más de 2 segmentos separados por coma (p.ej. "Campotenese, Parque Nacional del
    Pollino, Italia") se recorta al primero y al último ("Campotenese, Italia") — el
    detalle intermedio no aporta en un post corto."""
    loc = o.get("location") or ""
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if len(parts) > 2:
        return f"{parts[0]}, {parts[-1]}"
    return loc


def format_opportunity(
    o: dict[str, Any], *, buttons: bool = False, show_title: bool = True, show_type: bool = True,
) -> str:
    """Mensaje HTML para el canal de Telegram. Con `buttons=True` (publicación real en el
    canal) formulario/infopack se omiten del texto porque van como botones (ver
    `opportunity_keyboard`); con `buttons=False` (vista previa al coordinador, donde ese
    hueco de botones ya lo usa Enviar/Modificar/Cancelar) se quedan como texto. El contacto
    SIEMPRE va como texto, nunca como botón (ver `opportunity_keyboard`).
    `show_title=False`/`show_type=False`: la publicación real va con imagen (ver
    `opportunity_card.py`) y la bandera+título y la categoría ya están ahí — se omiten del
    pie para no repetirlos."""
    lines = []
    if show_title:
        lead = _flag(o.get("country_code")) or "🌍"
        lines.append(f"{lead} <b>{o['title']}</b>")
    if o.get("topic"):
        tema = f"🏷️ {_topic_label(o)}: {o['topic']}" if show_type else f"🏷️ Temática: {o['topic']}"
        lines.append(tema)
    if _place(o):
        lines.append(f"📍 {_place(o)}")
    lines.append(f"🗓️ {_compact_dates(o)}")
    if o.get("summary"):
        lines.append(f"\n{o['summary']}")
    if o.get("application_deadline"):
        lines.append(
            f"\n⏳ Fecha límite: <b>{o['application_deadline']}{_est(o)}</b> "
            f"({_days_left(o['application_deadline'])})"
        )
    app_url, info_url = o.get("application_url"), o.get("infopack_url")
    if not buttons:
        # Vista previa/edición: enlace clicable si es una URL de verdad; si no (el LLM a
        # veces mete un email o texto suelto), texto plano — nunca se pierde el dato, y
        # nunca se manda un <a href> roto.
        if app_url:
            lines.append(f'👉 <a href="{app_url}">Formulario de inscripción</a>' if _valid_url(app_url)
                          else f"👉 Formulario de inscripción: {app_url}")
        if info_url:
            lines.append(f'📄 <a href="{info_url}">Infopack</a>' if _valid_url(info_url)
                          else f"📄 Infopack: {info_url}")
    else:
        # Publicación real: si no valen como botón, que no desaparezcan sin más — texto.
        if app_url and not _valid_url(app_url):
            lines.append(f"👉 Formulario de inscripción: {app_url}")
        if info_url and not _valid_url(info_url):
            lines.append(f"📄 Infopack: {info_url}")
    if o.get("contact_information"):
        lines.append(f"✉️ {o['contact_information']}")
    return "\n".join(lines)


def format_hidden_fields(o: dict[str, Any]) -> str:
    """Campos que la IA extrae y el mapa usa de verdad (edad mín/máx para el filtro de edad,
    plazas, coste, organizador) pero que NUNCA aparecen en el texto publicado en el canal —
    `format_opportunity()` no los imprime porque ahí solo interesa lo esencial. El coordinador
    nunca los veía en la vista previa, así que no tenía forma de darse cuenta si la IA se
    equivocaba en uno de ellos (p.ej. una edad mínima mal leída) hasta que ya estaba publicado.
    Se muestran SOLO en la vista previa (nunca en el mensaje real del canal) y solo los que
    tengan dato — si no hay ninguno, no se añade nada."""
    rows = []
    if o.get("organiser_name"):
        rows.append(f"👤 Organiza: {o['organiser_name']}")
    if o.get("participant_min_age") is not None or o.get("participant_max_age") is not None:
        min_age, max_age = o.get("participant_min_age"), o.get("participant_max_age")
        if min_age is not None and max_age is not None:
            edad = f"{min_age}-{max_age} años"
        elif min_age is not None:
            edad = f"desde {min_age} años"
        else:
            edad = f"hasta {max_age} años"
        rows.append(f"🔞 Edad: {edad}")
    if o.get("max_participants") is not None:
        rows.append(f"👥 Plazas: {o['max_participants']}")
    if o.get("cost") is not None:
        coste = "Gratis" if float(o["cost"]) == 0 else f"{o['cost']}€"
        rows.append(f"💶 Coste: {coste}")
    if not rows:
        return ""
    return (
        "\n\n🔧 <b>Otros datos detectados</b> (no salen en el canal; se usan como filtros del mapa):\n"
        + "\n".join(rows)
    )


def format_opportunity_whatsapp(o: dict[str, Any]) -> str:
    """Texto compacto en formato WhatsApp (*negrita*, URLs en plano) para copiar y pegar en
    el canal de difusión. WhatsApp NO soporta texto-ancla (un link con una etiqueta propia
    como en HTML) en mensajes de texto normales — solo detecta URLs "en crudo" y las hace
    tocables tal cual. En vez de volcar los enlaces externos crudos (a veces larguísimos y
    feos, tipo Microsoft/Google Forms o descargas de SALTO con la URL escapada), se manda
    UN enlace limpio a la ficha en el mapa público (`?o=identifier`, deep link ya soportado
    por `mapa.html`: centra el pin y abre su popup con los botones reales de Infopack/Form)."""
    lines = [f"🌍 *{o['title']}*"]

    segs = [s for s in [
        f"🏷️ {_topic_label(o)}: {o['topic']}" if o.get("topic") else "",
        f"📍 {_place(o)}" if _place(o) else "",
        f"🗓️ {_compact_dates(o)}",
    ] if s]
    lines.append(" ".join(segs))

    if o.get("application_deadline"):
        lines.append(f"⏳ Límite *{o['application_deadline']}{_est(o)}*")

    app_url, info_url = o.get("application_url"), o.get("infopack_url")
    short_link = _short_map_link(o.get("identifier"))
    if app_url or info_url:
        label = "Infopack y form." if (app_url and info_url) else ("Formulario" if app_url else "Infopack")
        if short_link:
            lines.append(f"👉 {label} en: {short_link}")
        else:
            # Sin mapa configurado (p.ej. local sin MAP_PUBLIC_URL): no perder el dato,
            # enlaces crudos como respaldo.
            links = [app_url] if app_url == info_url else [u for u in [app_url, info_url] if u]
            lines.append(f"👉 {label}: " + " · ".join(links))
    elif short_link:
        # Sin formulario/infopack de verdad (p.ej. solo un "apúntate por Instagram" sin
        # URL) — el mapa sigue siendo útil (ubicación, fechas, contacto), así que TODA
        # oportunidad lleva enlace, no solo las que tienen enlace externo real.
        lines.append(f"🗺️ Más información en: {short_link}")

    if o.get("contact_information"):
        lines.append(f"✉️ {o['contact_information']}")
    return "\n".join(lines)


def _short_map_link(identifier: str | None) -> str | None:
    """Enlace corto tipo `mapa.proactivefuture.eu/2026-0040` (en vez de la URL con `?o=`) —
    más presentable para compartir a mano en WhatsApp. Redirige a la ficha en el mapa vía
    la ruta `/{short_id}` de `api/main.py`. `cfg.map_public_url` incluye un path propio
    (p.ej. `.../corradi-erasmus`), así que se reconstruye solo el origen (esquema+host)."""
    if not cfg.map_public_url or not identifier or not identifier.startswith("CORRADI-"):
        return None
    root = urlsplit(cfg.map_public_url)
    short_id = identifier.removeprefix("CORRADI-")
    return f"{root.scheme}://{root.netloc}/{short_id}"


def _channel_link(o: dict[str, Any]) -> str | None:
    """Enlace directo al post original en el canal (solo si es público y se guardó el message_id)."""
    if cfg.telegram_channel_username and o.get("telegram_message_id"):
        return f"https://t.me/{cfg.telegram_channel_username}/{o['telegram_message_id']}"
    return None


def _header(today: date) -> str:
    return (
        f"📅 <b>Resumen diario de oportunidades abiertas — "
        f"{today.day} de {_MESES[today.month - 1]} de {today.year}</b>"
    )


def format_summary_item(o: dict[str, Any], show_type: bool = True) -> str:
    """Bloque de una oportunidad. En el resumen diario va agrupada por tipo, así que ahí
    NO se repite el tipo en cada línea (show_type=False); en /editarmisproyectos la lista es
    plana y sí interesa verlo (show_type=True, por defecto)."""
    link = _channel_link(o)
    title = f'<a href="{link}">{o["title"]}</a>' if link else o["title"]
    if o.get("topic"):
        tema = f"🏷️ {_topic_label(o)}: {o['topic']}" if show_type else f"🏷️ {o['topic']}"
    else:
        tema = ""
    segs = [s for s in [
        tema,
        f"🌍 {_place(o)}" if _place(o) else "",
        f"📅 {_compact_dates(o)}",
    ] if s]
    return (
        f"• <b>{title}</b>\n{' '.join(segs)}\n"
        f"⏳ Fecha límite: {o['application_deadline']}{_est(o)} ({_days_left(o['application_deadline'])})"
    )


def format_daily_summary(opps: list[dict[str, Any]], today: date | None = None) -> str:
    """Resumen de TODAS las oportunidades que siguen ABIERTAS (fecha límite de inscripción aún
    no vencida), no solo las recibidas hoy, agrupadas por tipo (Youth Exchange, Training Course,
    ECS, Workshop). Cada título enlaza a su post original en el canal (si es público y se conoce
    su message_id), para poder encontrarla en el historial."""
    today = today or date.today()
    head = _header(today)
    if not opps:
        return f"{head}\n\n☀️ Ahora mismo no hay ninguna oportunidad con inscripción abierta. ¡Mañana más!"
    plural = len(opps) != 1
    parts = [
        head,
        f"☀️ {len(opps)} oportunidad{'es' if plural else ''} con inscripción abierta "
        f"ahora mismo:",
    ]

    by_type: dict[str | None, list[dict[str, Any]]] = {}
    for o in opps:
        by_type.setdefault(o.get("type"), []).append(o)

    for type_key, label in _GRUPOS_RESUMEN:
        items = by_type.pop(type_key, None)
        if not items:
            continue
        parts.append(f"<b>{label} ({len(items)})</b>")
        parts += [format_summary_item(o, show_type=False) for o in items]

    otros = [o for items in by_type.values() for o in items]
    if otros:
        parts.append(f"<b>📌 Otras ({len(otros)})</b>")
        parts += [format_summary_item(o, show_type=False) for o in otros]

    if cfg.map_public_url:
        parts.append(f'🗺️ <a href="{cfg.map_public_url}">Verlas todas en el mapa</a>')

    return "\n\n".join(parts)


def format_weekly_summary(
    published: int, open_count: int,
    countries: list[dict[str, Any]], types: list[dict[str, Any]],
    week_start: date, week_end: date,
) -> str:
    """Resumen semanal: nuevas publicadas + abiertas ahora mismo + top países/temáticas."""
    head = (
        f"📊 <b>Resumen semanal — {week_start.day} de {_MESES[week_start.month - 1]} "
        f"al {week_end.day} de {_MESES[week_end.month - 1]} de {week_end.year}</b>"
    )
    pub_pl = published != 1
    open_pl = open_count != 1
    lines = [
        head, "",
        f"✅ {published} oportunidad{'es' if pub_pl else ''} nueva{'s' if pub_pl else ''} "
        f"publicada{'s' if pub_pl else ''} esta semana",
        f"☀️ {open_count} abierta{'s' if open_pl else ''} ahora mismo",
    ]
    if countries:
        paises = " · ".join(
            f"{_flag(c['country_code'])} {_PAISES_ES.get(c['country_code'].upper(), c['country_code'])} ({c['n']})"
            for c in countries
        )
        lines.append(f"\n🌍 Top países: {paises}")
    if types:
        temas = " · ".join(f"{_TIPOS_ES.get(t['type'], t['type'])} ({t['n']})" for t in types)
        lines.append(f"🏷️ Por tipo: {temas}")
    if cfg.map_public_url:
        lines.append(f'\n🗺️ <a href="{cfg.map_public_url}">Ver todas en el mapa</a>')
    return "\n".join(lines)


def format_daily_summary_whatsapp(opps: list[dict[str, Any]]) -> str:
    if not opps:
        return "☀️ Ahora mismo no hay ninguna oportunidad con inscripción abierta. ¡Mañana más!"
    out = [f"☀️ *Oportunidades abiertas ({len(opps)})*\n"]
    for o in opps:
        bits = [b for b in [o.get("topic"), _place(o), _dates(o)] if b]
        dl = f" — hasta {o['application_deadline']}" if o.get("application_deadline") else ""
        out.append(f"• *{o['title']}* ({' · '.join(bits)}){dl}")
    return "\n".join(out)


_WHATSAPP_DIGEST_MAX_LEN = 3500  # margen bajo el límite real de Telegram (4096) para el DM


def format_daily_digest_whatsapp(opps: list[dict[str, Any]]) -> str:
    """Resumen diario en formato WhatsApp de SOLO lo publicado hoy (no lo abierto en
    general), pensado para copiar y pegar a mano en el canal de difusión de WhatsApp
    (no automatizable, ver `handoff.py`). Se manda por DM a los admins vía `notify_admin`.

    Recorta si hace falta en vez de trocear en varios DMs (a diferencia de
    `send_chunked_dm`): el mensaje se copia y pega ENTERO a mano en WhatsApp, así que tiene
    que quedarse en UNA sola pieza — un día con muchas publicaciones no debe tumbar el envío
    entero con "BadRequest: Message is too long" (visto en producción)."""
    if not opps:
        return "☀️ Resumen del día — ninguna oportunidad nueva hoy."
    plural = len(opps) != 1
    parts = [f"☀️ Resumen del día — Nueva{'s' if plural else ''} oportunidad{'es' if plural else ''}: {len(opps)}"]
    included = 0
    for o in opps:
        entry = format_opportunity_whatsapp(o)
        if included > 0 and len("\n\n".join(parts + [entry])) > _WHATSAPP_DIGEST_MAX_LEN:
            break
        parts.append(entry)
        included += 1
    if included < len(opps):
        remaining = len(opps) - included
        link = cfg.map_public_url or "el mapa"
        parts.append(f"➕ {remaining} oportunidad{'es' if remaining != 1 else ''} más hoy — mira el mapa: {link}")
    return "\n\n".join(parts)


def _theme_groups_lines(opps: list[dict[str, Any]], max_per_group: int = 20) -> list[str]:
    """Líneas del bloque agrupado por TEMÁTICA similar (`_classify_topic`, no por las 4
    categorías fijas de tipo), con una línea en blanco entre grupos para que respiren. Un
    tema con una sola ficha no es un grupo real, así que se funde en `_OTRAS_TEMA` en vez de
    mostrarse suelto. `max_per_group` es un tope de seguridad por si algún grupo crece
    mucho: se recortan los últimos con un "+N más" para no arriesgar el límite de 4096
    caracteres de Telegram. Compartido por `format_weekly_topics_summary` (standalone) y
    `format_weekly_full_summary` (el resumen semanal combinado que de verdad se publica)."""
    if not opps:
        return ["Ahora mismo no hay ninguna oportunidad con inscripción abierta."]

    by_theme: dict[str, list[dict[str, Any]]] = {}
    for o in opps:
        by_theme.setdefault(_classify_topic(o.get("topic")), []).append(o)

    otras = by_theme.pop(_OTRAS_TEMA, [])
    for label in [l for l, items in by_theme.items() if len(items) == 1]:
        otras += by_theme.pop(label)

    def _item_line(o: dict[str, Any]) -> str:
        link = _channel_link(o)
        title = f'<a href="{link}">{o["title"]}</a>' if link else o["title"]
        return f"• {title}"

    groups = sorted(by_theme.items(), key=lambda kv: -len(kv[1]))
    if otras:
        groups.append((_OTRAS_TEMA, otras))

    lines: list[str] = []
    for i, (label, items) in enumerate(groups):
        if i > 0:
            lines.append("")  # espacio entre temáticas
        lines.append(f"<b>{label} ({len(items)})</b>")
        lines += [_item_line(o) for o in items[:max_per_group]]
        if len(items) > max_per_group:
            lines.append(f"+{len(items) - max_per_group} más en este grupo")
    return lines


def format_weekly_topics_summary(opps: list[dict[str, Any]], max_per_group: int = 20) -> str:
    """Resumen semanal agrupado por temática, standalone (con su propia cabecera y conteo)
    — ver `_theme_groups_lines` para el cuerpo. La entrega real los combina en un único
    mensaje (`format_weekly_full_summary`); esta función se conserva para tests/reuso."""
    head = "📊 <b>Resumen semanal — temáticas</b>"
    if not opps:
        return f"{head}\n\nAhora mismo no hay ninguna oportunidad con inscripción abierta."
    plural = len(opps) != 1
    lines = [head, f"{len(opps)} oportunidad{'es' if plural else ''} abierta{'s' if plural else ''} ahora mismo", ""]
    lines += _theme_groups_lines(opps, max_per_group)
    if cfg.map_public_url:
        lines.append(f'\n🗺️ <a href="{cfg.map_public_url}">Ver todas en el mapa</a>')
    return "\n".join(lines)


def _week_range_label(week_start: date, week_end: date) -> str:
    if week_start.month == week_end.month:
        return f"{week_start.day} - {week_end.day} de {_MESES[week_start.month - 1]}"
    return (f"{week_start.day} {_MES_ABBR[week_start.month - 1]} - "
            f"{week_end.day} de {_MESES[week_end.month - 1]}")


def format_weekly_full_summary(
    open_count: int,
    countries: list[dict[str, Any]], types: list[dict[str, Any]],
    week_start: date, week_end: date,
    open_opps: list[dict[str, Any]], max_per_group: int = 20,
) -> str:
    """Resumen semanal ÚNICO (antes eran dos mensajes de domingo separados, fusionados a
    petición del usuario): abiertas ahora mismo + top países/tipos, seguido del agrupado
    por temática de todo lo abierto. El conteo de "nuevas publicadas esta semana" se quitó
    del texto a petición del usuario (2026-07-25) — se sigue calculando y registrando en el
    log del scheduler, solo no se muestra en el mensaje."""
    head = f"📊 <b>RESUMEN SEMANAL · {_week_range_label(week_start, week_end)}</b>"
    open_pl = open_count != 1
    lines = [
        head, "",
        f"☀️ {open_count} abierta{'s' if open_pl else ''} ahora mismo. "
        f"Los domingos te las recordamos todas agrupadas por TEMÁTICA:",
    ]
    if countries:
        paises = " · ".join(
            f"{_flag(c['country_code'])} {_PAISES_ES.get(c['country_code'].upper(), c['country_code'])} ({c['n']})"
            for c in countries
        )
        lines.append(f"\n🌍 Top países: {paises}")
    if types:
        temas = " · ".join(f"{_TIPOS_ES.get(t['type'], t['type'])} ({t['n']})" for t in types)
        lines.append(f"🏷️ Por tipo: {temas}")

    lines.append("")
    lines += _theme_groups_lines(open_opps, max_per_group)

    if cfg.map_public_url:
        lines.append(f'\n🗺️ <a href="{cfg.map_public_url}">Ver todas en el mapa</a>')
    return "\n".join(lines)


async def publish_to_channel(text: str, reply_markup: InlineKeyboardMarkup | None = None) -> int | None:
    """Publica en el canal. Devuelve el message_id (para enlazarla luego) o None si no hay
    canal configurado todavía."""
    if not cfg.telegram_channel_id:
        return None
    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(cfg.telegram_bot_token)
    msg = await bot.send_message(
        chat_id=cfg.telegram_channel_id, text=text,
        parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=reply_markup,
    )
    return msg.message_id


async def publish_photo_to_channel(
    photo: bytes, caption: str, reply_markup: InlineKeyboardMarkup | None = None,
) -> int | None:
    """Publica en el canal como foto+pie (imagen de `opportunity_card.render()`). Igual que
    `publish_to_channel` pero con `send_photo`; el pie tiene el límite de Telegram de 1024
    caracteres (los mensajes de solo texto llegan a 4096) — hay margen de sobra porque el
    pie ya no lleva bandera+título ni la categoría (van en la imagen)."""
    if not cfg.telegram_channel_id:
        return None
    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(cfg.telegram_bot_token)
    msg = await bot.send_photo(
        chat_id=cfg.telegram_channel_id, photo=photo, caption=caption,
        parse_mode=ParseMode.HTML, reply_markup=reply_markup,
    )
    return msg.message_id


async def notify_admin(admin_id: int, text: str) -> None:
    """Manda un aviso por DM a un admin (p.ej. veto automático por spam)."""
    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(cfg.telegram_bot_token)
    await bot.send_message(
        chat_id=admin_id, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )


_DM_MAX_LEN = 3900  # margen de seguridad bajo el límite real de Telegram (4096)


async def send_chunked_dm(admin_id: int, text: str) -> None:
    """Como `notify_admin`, pero trocea en varios DMs si `text` no cabe en un solo mensaje
    de Telegram — cortando siempre por saltos de línea completos, nunca a mitad de una
    línea. Encontrado en pruebas reales del scraper de SALTO-YOUTH: una descripción larga
    (objetivos, perfil de participantes, costes...) tumbaba el envío entero con
    `BadRequest: Message is too long`."""
    if len(text) <= _DM_MAX_LEN:
        await notify_admin(admin_id, text)
        return
    chunk = ""
    for line in text.split("\n"):
        candidate = f"{chunk}\n{line}" if chunk else line
        if len(candidate) > _DM_MAX_LEN:
            if chunk:
                await notify_admin(admin_id, chunk)
            chunk = line
        else:
            chunk = candidate
    if chunk:
        await notify_admin(admin_id, chunk)


async def send_to_handoff_group(whatsapp_text: str) -> None:
    """Manda al grupo privado de admins (Telegram) el texto en formato WhatsApp, listo para pegar."""
    if not cfg.whatsapp_handoff_group_id:
        return
    from telegram import Bot

    bot = Bot(cfg.telegram_bot_token)
    await bot.send_message(
        chat_id=cfg.whatsapp_handoff_group_id,
        text="📋 Copia y pega esto en el canal de WhatsApp:\n\n" + whatsapp_text,
        disable_web_page_preview=True,
    )
