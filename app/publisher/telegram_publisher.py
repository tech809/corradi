"""Formatea y publica oportunidades en Telegram y prepara el handoff a WhatsApp."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.config import cfg

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
    "WORKSHOP": "Workshop",
}

# Etiqueta que sustituye a "Temática" en la línea 🏷️ de cada oportunidad.
_TIPO_LABEL_TEMA = {
    "YOUTH_EXCHANGE": "Youth Exchange",
    "TRAINING_COURSE": "Training Course",
    "VOLUNTEERING": "ECS",
    "WORKSHOP": "Workshop",
}

# Orden y cabecera visual de los grupos del resumen diario.
_GRUPOS_RESUMEN = [
    ("YOUTH_EXCHANGE", "🎒 Youth Exchange"),
    ("TRAINING_COURSE", "🎓 Training Course"),
    ("VOLUNTEERING", "🤝 ECS"),
    ("WORKSHOP", "🛠️ Workshop"),
]


def _topic_label(o: dict[str, Any]) -> str:
    return _TIPO_LABEL_TEMA.get(o.get("type"), "Temática")


def _flag(country_code: str | None) -> str:
    """Emoji de bandera a partir de un código ISO 3166-1 alpha-2 (p.ej. 'DE' -> 🇩🇪)."""
    if not country_code or len(country_code) != 2 or not country_code.isalpha():
        return ""
    cc = country_code.upper()
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in cc)


def _dates(o: dict[str, Any]) -> str:
    s, e = o.get("start_date"), o.get("end_date")
    if s and e:
        return f"{s} → {e}"
    return str(s or e or "fechas por confirmar")


def _place(o: dict[str, Any]) -> str:
    return o.get("location") or ""


def format_opportunity(o: dict[str, Any]) -> str:
    """Mensaje HTML para el canal de Telegram."""
    lead = _flag(o.get("country_code")) or "🌍"
    lines = [f"{lead} <b>{o['title']}</b>"]
    if o.get("topic"):
        lines.append(f"🏷️ {_topic_label(o)}: {o['topic']}")
    if _place(o):
        lines.append(f"📍 {_place(o)}")
    lines.append(f"🗓️ {_dates(o)}")
    if o.get("summary"):
        lines.append(f"\n{o['summary']}")
    if o.get("application_deadline"):
        est = " (estimada)" if o.get("deadline_estimated") else ""
        lines.append(f"\n⏳ Inscripción hasta: <b>{o['application_deadline']}{est}</b>")
    if o.get("application_url"):
        lines.append(f'👉 <a href="{o["application_url"]}">Formulario de inscripción</a>')
    if o.get("infopack_url"):
        lines.append(f'📄 <a href="{o["infopack_url"]}">Infopack</a>')
    if o.get("contact_information"):
        lines.append(f"✉️ {o['contact_information']}")
    return "\n".join(lines)


def format_opportunity_whatsapp(o: dict[str, Any]) -> str:
    """Texto en formato WhatsApp (*negrita*, URLs en plano) para copiar y pegar."""
    lines = [f"🌍 *{o['title']}*"]
    if o.get("topic"):
        lines.append(f"🏷️ {_topic_label(o)}: {o['topic']}")
    if _place(o):
        lines.append(f"📍 {_place(o)}")
    lines.append(f"🗓️ {_dates(o)}")
    if o.get("summary"):
        lines.append(f"\n{o['summary']}")
    if o.get("application_deadline"):
        est = " (estimada)" if o.get("deadline_estimated") else ""
        lines.append(f"⏳ Inscripción hasta: *{o['application_deadline']}{est}*")
    if o.get("application_url"):
        lines.append(f"👉 {o['application_url']}")
    if o.get("infopack_url"):
        lines.append(f"📄 {o['infopack_url']}")
    if o.get("contact_information"):
        lines.append(f"✉️ {o['contact_information']}")
    return "\n".join(lines)


def _channel_link(o: dict[str, Any]) -> str | None:
    """Enlace directo al post original en el canal (solo si es público y se guardó el message_id)."""
    if cfg.telegram_channel_username and o.get("telegram_message_id"):
        return f"https://t.me/{cfg.telegram_channel_username}/{o['telegram_message_id']}"
    return None


def _header(today: date) -> str:
    return f"📅 <b>Resumen diario — {today.day} de {_MESES[today.month - 1]} de {today.year}</b>"


def format_summary_item(o: dict[str, Any]) -> str:
    """Bloque de 3 líneas para una oportunidad (usado en el resumen diario y en /buscar)."""
    link = _channel_link(o)
    title = f'<a href="{link}">{o["title"]}</a>' if link else o["title"]
    segs = [s for s in [
        f"🏷️ {_topic_label(o)}: {o['topic']}" if o.get("topic") else "",
        f"🌍 {_place(o)}" if _place(o) else "",
        f"📅 {_dates(o)}",
    ] if s]
    est = " (estimada)" if o.get("deadline_estimated") else ""
    return (
        f"• <b>{title}</b>\n{' '.join(segs)}\n"
        f"⏳ Fecha límite inscripción: {o['application_deadline']}{est}"
    )


def format_daily_summary(opps: list[dict[str, Any]], today: date | None = None) -> str:
    """Resumen de las oportunidades ABIERTAS, agrupadas por tipo (Youth Exchange, Training
    Course, ECS, Workshop). Cada título enlaza a su post original en el canal (si es público
    y se conoce su message_id), para poder encontrarla en el historial."""
    today = today or date.today()
    head = _header(today)
    if not opps:
        return f"{head}\n\n☀️ Hoy no hay oportunidades abiertas nuevas. ¡Mañana más!"
    plural = len(opps) != 1
    parts = [head, f"☀️ {len(opps)} oportunidad{'es' if plural else ''} abierta{'s' if plural else ''}"]

    by_type: dict[str | None, list[dict[str, Any]]] = {}
    for o in opps:
        by_type.setdefault(o.get("type"), []).append(o)

    for type_key, label in _GRUPOS_RESUMEN:
        items = by_type.pop(type_key, None)
        if not items:
            continue
        parts.append(f"<b>{label} ({len(items)})</b>")
        parts += [format_summary_item(o) for o in items]

    otros = [o for items in by_type.values() for o in items]
    if otros:
        parts.append(f"<b>📌 Otras ({len(otros)})</b>")
        parts += [format_summary_item(o) for o in otros]

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
        lines.append(f"🏷️ Top temáticas: {temas}")
    return "\n".join(lines)


def format_daily_summary_whatsapp(opps: list[dict[str, Any]]) -> str:
    if not opps:
        return "☀️ Hoy no hay oportunidades abiertas nuevas. ¡Mañana más!"
    out = [f"☀️ *Oportunidades abiertas ({len(opps)})*\n"]
    for o in opps:
        bits = [b for b in [o.get("topic"), _place(o), _dates(o)] if b]
        dl = f" — hasta {o['application_deadline']}" if o.get("application_deadline") else ""
        out.append(f"• *{o['title']}* ({' · '.join(bits)}){dl}")
    return "\n".join(out)


async def publish_to_channel(text: str) -> int | None:
    """Publica en el canal. Devuelve el message_id (para enlazarla luego) o None si no hay
    canal configurado todavía."""
    if not cfg.telegram_channel_id:
        return None
    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(cfg.telegram_bot_token)
    msg = await bot.send_message(
        chat_id=cfg.telegram_channel_id, text=text,
        parse_mode=ParseMode.HTML, disable_web_page_preview=True,
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
