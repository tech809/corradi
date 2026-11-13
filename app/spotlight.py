"""Mensaje semanal rotativo: cada semana un tema distinto.

Modo mixto, para no publicar nunca un dato falso:
- El CUERPO (cifras, títulos, fechas, plazos, enlaces) lo escribe el código a partir de la
  BD, con varias frases posibles por dato para que no se repita siempre igual.
- La IA solo escribe el GANCHO inicial y el CIERRE, sin datos: se rechaza cualquier texto
  con cifras, enlaces o frases vetadas. Si la IA falla o no está disponible, se usa un
  gancho/cierre de reserva escrito a mano, así que el mensaje sale igual.

Todo se escribe en un markdown mínimo (**negrita** y [texto](url)); el HTML de Telegram y el
texto de WhatsApp se generan aquí, escapados.
"""
from __future__ import annotations

import html
import json
import logging
import math
import random
import re
from datetime import date, timedelta
from typing import Any

from psycopg.rows import dict_row

from app.config import cfg
from app.db.pool import get_pool
from app.publisher import telegram_publisher as pub

log = logging.getLogger("corradi.spotlight")

# Orden de rotación (semana ISO % len). Si un tema no tiene datos, se usa el siguiente.
THEMES = ("datos", "records", "destino", "erasmus", "ultima_llamada", "estreno")

_MADRID = (40.4168, -3.7038)
# «Destino exótico» = fuera de la UE/EEE, Reino Unido y Suiza (Turquía, Armenia, Egipto…).
_COMMON = frozenset("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI "
                    "ES SE IS LI NO GB UK CH".split())
_MAX_VISIBLE = 1800

# Datos estables del programa (Guía Erasmus+ y Guía del Cuerpo Europeo de Solidaridad).
# Son la ÚNICA fuente del tema «erasmus». Revisar antes de cambiar.
ERASMUS_FACTS = [
    "Un **Youth Exchange** reúne a grupos de jóvenes de varios países para convivir y "
    "trabajar un tema con educación no formal. Dura entre 5 y 21 días, sin contar el "
    "viaje, y es para jóvenes de 13 a 30 años.",
    "Un **Training Course** es una formación para quien trabaja con jóvenes: monitores, "
    "educadores, voluntarios de asociaciones…",
    "El **voluntariado ESC** (Cuerpo Europeo de Solidaridad) es para personas de 18 a 30 "
    "años. Puede ser largo (de 2 a 12 meses) o corto (de 2 semanas a 2 meses).",
    "En el **voluntariado ESC** el programa cubre el viaje, el alojamiento, la comida, el "
    "seguro y un dinero de bolsillo mensual.",
    "En los proyectos Erasmus+ de juventud el **viaje** se cubre con un importe según la "
    "distancia, y si viajas de forma sostenible (tren, autobús, coche compartido) el "
    "importe es mayor.",
    "**Youthpass** es el certificado europeo que reconoce lo que aprendes en un Youth "
    "Exchange, un Training Course o un voluntariado ESC.",
    "Para ir a un Youth Exchange o un Training Course normalmente te envía una "
    "**organización de tu país** que es socia del proyecto (la «sending organisation»).",
    "El **infopack** es el documento con todos los detalles del proyecto: fechas, lugar, "
    "perfil de participantes, costes cubiertos y cómo inscribirse.",
    "Los proyectos de juventud tienen **apoyo extra para participantes con menos "
    "oportunidades**, para que el dinero o la situación personal no sean una barrera.",
]

_TYPE_ES = {"YOUTH_EXCHANGE": "Youth Exchange", "TRAINING_COURSE": "Training Course",
            "VOLUNTEERING": "Voluntariado ESC"}
_LISTABLE = ("YOUTH_EXCHANGE", "TRAINING_COURSE")
_OPEN = "status='open' AND (application_deadline IS NULL OR application_deadline >= %s)"


# ---------------------------------------------------------------- utilidades de formato

def theme_for(today: date) -> str:
    return THEMES[today.isocalendar().week % len(THEMES)]


# Países que no están en telegram_publisher._PAISES_ES (sobre todo los de fuera de la UE).
_EXTRA_PAISES = {
    "EG": "Egipto", "AM": "Armenia", "GE": "Georgia", "TN": "Túnez", "MA": "Marruecos",
    "JO": "Jordania", "LB": "Líbano", "UA": "Ucrania", "MD": "Moldavia", "AL": "Albania",
    "MK": "Macedonia del Norte", "XK": "Kosovo", "BA": "Bosnia y Herzegovina",
    "ME": "Montenegro", "AZ": "Azerbaiyán", "RS": "Serbia", "TR": "Turquía", "IL": "Israel",
    "PS": "Palestina", "DZ": "Argelia", "LY": "Libia", "BY": "Bielorrusia", "RU": "Rusia",
    "KZ": "Kazajistán", "IS": "Islandia", "NO": "Noruega", "LI": "Liechtenstein",
    "CH": "Suiza", "GB": "Reino Unido", "UK": "Reino Unido",
}


# ESC individual: de 2 a 12 meses. Algunas fichas del portal traen la ventana de la
# convocatoria (p. ej. 19 meses) en vez de la estancia: no se usan para récords ni medias.
_ESC_MAX_MONTHS = 12


def _country(code: str | None) -> str:
    cc = (code or "").upper()
    if cc in _EXTRA_PAISES:
        return _EXTRA_PAISES[cc]
    name = pub._PAISES_ES.get(cc) or cc
    # _PAISES_ES va sin espacios (sirve para hashtags): «PaísesBajos» → «Países Bajos».
    name = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", name)
    return re.sub(r" (Del|De|Y) ", lambda m: f" {m.group(1).lower()} ", name)


def _flag(code: str | None) -> str:
    return pub._flag(code) or "🌍"


def _place(row: dict[str, Any]) -> str:
    """«Ciudad, País» con el país en español (la BD trae a veces «Pignola, Italy»)."""
    country = _country(row.get("country_code"))
    city = (row.get("location") or "").split(",")[0].strip()
    if city.lower() in (country.lower(), (row.get("country_code") or "").lower()):
        city = ""
    return ", ".join(x for x in (city, country) if x) or "Destino por confirmar"


def _title_link(row: dict[str, Any]) -> str:
    title = " ".join(str(row["title"]).split()).replace("[", "(").replace("]", ")")
    link = pub._short_map_link(row.get("identifier"))
    return f"**[{title}]({link})**" if link else f"**{title}**"


def _long_date(d: date) -> str:
    return f"{d.day} de {pub._MESES[d.month - 1]}"


def _dates(row: dict[str, Any]) -> str:
    return pub._compact_dates(row)


def _deadline(row: dict[str, Any], today: date) -> str:
    d = row.get("application_deadline")
    if not d:
        return "plazo sin confirmar"
    return f"plazo {pub._deadline_short(d)} · {pub._days_left(d, today)}"


def _num(x: float) -> str:
    """6.7 → «6,7»; 7.0 → «7»."""
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _km_from_madrid(row: dict[str, Any]) -> int | None:
    if row.get("latitude") is None or row.get("longitude") is None:
        return None
    lat1, lon1 = map(math.radians, _MADRID)
    lat2, lon2 = math.radians(float(row["latitude"])), math.radians(float(row["longitude"]))
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return round(6371 * 2 * math.asin(math.sqrt(a)))


def _km(n: int) -> str:
    return f"{n:,}".replace(",", ".")


async def _rows(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            return list(await cur.fetchall())


async def _open_by_type(today: date) -> dict[str, int]:
    rows = await _rows(f"SELECT type, count(*)::int n FROM projects WHERE {_OPEN} GROUP BY type", (today,))
    return {r["type"]: r["n"] for r in rows if r["type"]}


def _counts_line(by_type: dict[str, int]) -> str:
    parts = [
        f"**{_plural(by_type.get('YOUTH_EXCHANGE', 0), 'Youth Exchange', 'Youth Exchanges')}**",
        f"**{_plural(by_type.get('TRAINING_COURSE', 0), 'Training Course', 'Training Courses')}**",
        f"**{_plural(by_type.get('VOLUNTEERING', 0), 'voluntariado ESC', 'voluntariados ESC')}**",
    ]
    return f"{parts[0]}, {parts[1]} y {parts[2]}"


# ---------------------------------------------------------------- cuerpos (solo código)

async def body_for(theme: str, today: date, rng: random.Random) -> tuple[str, str] | None:
    """(cuerpo, contexto_para_la_IA) del tema, o None si no hay nada que contar.

    El contexto son palabras sin cifras para que el gancho venga a cuento (p. ej. el país
    del destino). Nunca se le pasan cifras ni fechas a la IA.
    """
    if theme == "datos":
        by_type = await _open_by_type(today)
        countries = await _rows(
            f"SELECT country_code, count(*)::int n FROM projects WHERE {_OPEN} "
            "AND country_code IS NOT NULL GROUP BY country_code ORDER BY n DESC", (today,))
        if not countries:
            return None
        listable = await _rows(
            f"SELECT country_code, count(*)::int n FROM projects WHERE {_OPEN} "
            "AND type = ANY(%s) AND country_code IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT 1",
            (today, list(_LISTABLE)))
        week = (await _rows(
            f"SELECT count(*)::int n FROM projects WHERE {_OPEN} AND application_deadline <= %s",
            (today, today + timedelta(days=7))))[0]["n"]
        esc = (await _rows(
            f"SELECT avg(duration_months)::float m FROM projects WHERE {_OPEN} "
            "AND type='VOLUNTEERING' AND duration_months BETWEEN 1 AND %s", (today, _ESC_MAX_MONTHS)))[0]["m"]
        top3 = " · ".join(f"{_flag(c['country_code'])} {_country(c['country_code'])} ({c['n']})"
                          for c in countries[:3])
        pool = [
            f"📌 Ahora mismo tienes abiertos {_counts_line(by_type)}.",
            f"🌍 Hay oportunidades abiertas en **{len(countries)} países**. Los que más tienen: {top3}.",
        ]
        if week:
            pool.append(f"⏳ **{_plural(week, 'oportunidad cierra', 'oportunidades cierran')}** en los próximos 7 días.")
        if esc:
            pool.append(f"🤝 Un voluntariado ESC abierto dura de media **{_num(esc)} meses**.")
        if listable:
            c = listable[0]
            pool.append(f"{_flag(c['country_code'])} El país con más Youth Exchanges y Training Courses "
                        f"abiertos es **{_country(c['country_code'])}** ({c['n']}).")
        lines = [pool[0]] + rng.sample(pool[1:], min(2, len(pool) - 1))
        return "\n\n".join(lines), "cifras del catálogo de oportunidades abiertas"

    if theme == "records":
        pool: list[str] = []
        total = (await _rows(
            "SELECT count(*)::int n, min(created)::date desde FROM projects"))[0]
        if total["desde"]:
            d = total["desde"]
            pool.append(f"📚 Desde {pub._MESES[d.month - 1]} de {d.year} han pasado por Corradi "
                        f"**{_km(total['n'])} oportunidades**.")
        best = await _rows(
            "SELECT date_trunc('week', created)::date semana, count(*)::int n FROM projects "
            "WHERE published_telegram GROUP BY 1 ORDER BY n DESC LIMIT 1")
        if best:
            pool.append(f"🏆 Semana récord: **{best[0]['n']} oportunidades** publicadas en el canal "
                        f"la semana del {_long_date(best[0]['semana'])}.")
        top_country = await _rows(
            "SELECT country_code, count(*)::int n FROM projects WHERE country_code IS NOT NULL "
            "GROUP BY 1 ORDER BY n DESC LIMIT 1")
        if top_country:
            c = top_country[0]
            pool.append(f"{_flag(c['country_code'])} **{_country(c['country_code'])}** es el país del que "
                        f"más oportunidades hemos tenido: **{_km(c['n'])}**.")
        viewed = await _rows(
            "SELECT p.*, SUM(i.count)::int vistas FROM projects p JOIN project_interactions i "
            "ON i.project_id=p.id WHERE i.kind='view' AND p.status='open' "
            "AND (p.application_deadline IS NULL OR p.application_deadline >= %s) "
            "GROUP BY p.id ORDER BY vistas DESC LIMIT 1", (today,))
        if viewed:
            r = viewed[0]
            pool.append(f"👀 La oportunidad abierta más vista: {_title_link(r)}, en {_place(r)} "
                        f"({_deadline(r, today)}).")
        open_geo = await _rows(f"SELECT * FROM projects WHERE {_OPEN} AND latitude IS NOT NULL", (today,))
        far = max(open_geo, key=lambda r: _km_from_madrid(r) or 0, default=None)
        if far and _km_from_madrid(far):
            pool.append(f"✈️ La más lejana que tienes abierta: {_title_link(far)}, en {_place(far)}, "
                        f"a **{_km(_km_from_madrid(far))} km** de Madrid.")
        longest = await _rows(
            f"SELECT * FROM projects WHERE {_OPEN} AND type='VOLUNTEERING' "
            "AND duration_months <= %s ORDER BY duration_months DESC LIMIT 1", (today, _ESC_MAX_MONTHS))
        if longest:
            r = longest[0]
            pool.append(f"⌛ El voluntariado abierto más largo: {_title_link(r)}, en {_place(r)}, "
                        f"de **{_num(float(r['duration_months']))} meses**.")
        if len(pool) < 2:
            return None
        return "\n\n".join(rng.sample(pool, min(3, len(pool)))), "curiosidades y récords de Corradi"

    if theme == "destino":
        rows = await _rows(
            f"SELECT * FROM projects WHERE {_OPEN} AND latitude IS NOT NULL AND country_code IS NOT NULL",
            (today,))
        far = sorted((r for r in rows if r["country_code"].upper() not in _COMMON),
                     key=lambda r: -(_km_from_madrid(r) or 0))
        if not far:
            return None
        # Preferimos YE/TC (más accesibles); si no hay, vale un ESC.
        pool = [r for r in far if r.get("type") in _LISTABLE] or far
        r = rng.choice(pool[:8])
        summary = " ".join(str(r.get("summary") or "").split())
        lines = [
            f"{_flag(r.get('country_code'))} {_title_link(r)}",
            f"📍 {_place(r)} · a {_km(_km_from_madrid(r))} km de Madrid",
            f"🏷️ {_TYPE_ES.get(r.get('type'), r.get('type') or '')} · 🗓️ {_dates(r)}",
            f"⏳ {_deadline(r, today)[0].upper()}{_deadline(r, today)[1:]}",
        ]
        if summary:
            lines += ["", summary[:350].rsplit(" ", 1)[0] + "…" if len(summary) > 350 else summary]
        return "\n".join(lines), f"destino lejano: {_place(r)}"

    if theme == "erasmus":
        facts = rng.sample(ERASMUS_FACTS, 2)
        by_type = await _open_by_type(today)
        lines = [f"💡 {f}" for f in facts]
        lines.append(f"🔎 Ahora mismo hay abiertos {_counts_line(by_type)}.")
        return "\n\n".join(lines), "cómo funciona Erasmus+ para quien empieza"

    if theme == "ultima_llamada":
        rows = await _rows(
            f"SELECT * FROM projects WHERE {_OPEN} AND application_deadline <= %s "
            "ORDER BY application_deadline, created", (today, today + timedelta(days=7)))
        listed = [r for r in rows if r.get("type") in _LISTABLE]
        if not listed:
            return None
        lines = [f"• {_title_link(r)}\n   {_flag(r.get('country_code'))} {_country(r.get('country_code'))} · "
                 f"{_TYPE_ES.get(r['type'])} · {_deadline(r, today)}" for r in listed[:6]]
        if len(listed) > 6:
            lines.append(f"• y {_plural(len(listed) - 6, 'otra', 'otras')} más en el mapa")
        esc = len(rows) - len(listed)
        if esc:
            lines.append(f"\n🤝 Además, **{_plural(esc, 'voluntariado ESC cierra', 'voluntariados ESC cierran')}** esta semana.")
        return "\n".join(lines), "oportunidades que cierran en pocos días"

    if theme == "estreno":
        rows = await _rows(
            f"SELECT * FROM projects WHERE {_OPEN} AND type='YOUTH_EXCHANGE' "
            "AND start_date > %s AND end_date - start_date <= 9 "
            "ORDER BY application_deadline NULLS LAST LIMIT 3", (today, today))
        if not rows:
            return None
        lines = [f"• {_title_link(r)}\n   {_flag(r.get('country_code'))} {_place(r)} · "
                 f"{(r['end_date'] - r['start_date']).days + 1} días ({_dates(r)}) · {_deadline(r, today)}"
                 for r in rows]
        return "\n".join(lines), "Youth Exchanges cortos, buenos para estrenarse en Erasmus+"

    raise ValueError(theme)


# ---------------------------------------------------------------- gancho y cierre (IA)

FALLBACK_HOOKS = {
    "datos": ["¿Te has preguntado cuántas puertas tienes abiertas ahora mismo? 👀",
              "Foto rápida de lo que hay en el mapa estos días 📸"],
    "records": ["Hoy toca mirar atrás un momento… y presumir un poco 😎",
                "Algunas curiosidades de Corradi que quizá no conocías 🤓"],
    "destino": ["¿Y si tu próxima aventura fuera bastante más lejos de lo habitual? ✈️",
                "Hoy te proponemos salir del mapa de siempre 🌍"],
    "erasmus": ["¿Te suena Erasmus+ pero no sabes muy bien cómo funciona? Te lo contamos fácil 👇",
                "Dos cosas sobre Erasmus+ que conviene saber antes de apuntarte 💡"],
    "ultima_llamada": ["Última llamada ⏰ Estas cierran en pocos días:",
                       "Si llevabas tiempo pensándotelo, es ahora o nunca ⏳"],
    "estreno": ["¿Nunca has ido a un Erasmus+? Un intercambio corto es la mejor forma de probar 🎒",
                "Para estrenarte sin miedo: intercambios cortitos 👇"],
}
FALLBACK_CLOSINGS = ["¿Te animas? 😉", "Si alguna te encaja, no lo dejes para mañana 🚀",
                     "Compártelo con quien le pueda venir bien 🙌", "Nos vemos en el mapa 🗺️"]

_ANGLES = {
    "datos": "una foto de cuántas oportunidades hay abiertas",
    "records": "curiosidades y récords del proyecto",
    "destino": "una oportunidad en un destino lejano y poco habitual",
    "erasmus": "explicar cómo funciona Erasmus+ a quien empieza",
    "ultima_llamada": "oportunidades que cierran en pocos días",
    "estreno": "intercambios cortos, buenos para un primer Erasmus+",
}
_STYLES = ("con una pregunta concreta", "con una frase corta y directa", "como un consejo entre amigos",
           "con humor suave", "con una exclamación y un emoji", "con un tono tranquilo y cercano",
           "con una imagen visual (maleta, mapa, billete…)", "con un «plan» para estos días")
_BANNED = re.compile(
    r"autom[aá]tic|generad|intelig|\bIA\b|semanal|cada semana|tema|plazas? limitad|gratis|"
    r"garantiz|millones|mundial|cansad[oa]|gast(?:ar|o|os|arte)\b|dinero|cambi\w* la vida|preparad[oae]s?\b|[uú]nic[oa]s?\b|\bspread\b|\blove\b|\blist[oa]s?\b|aburrid|aventurer|\bchic[oa]s\b|\bhttp|www\.|\[|\]", re.I)


def build_prompt(theme: str, context: str, rng: random.Random) -> str:
    return f"""Eres quien escribe el canal de Corradi, que difunde oportunidades Erasmus+
(Youth Exchanges, Training Courses y voluntariados ESC) entre jóvenes de España.

Debajo de lo que escribas irá un bloque con los datos ({_ANGLES[theme]}; contexto: {context}).
Escribe SOLO:
- "gancho": la frase de entrada, {rng.choice(_STYLES)}. Máximo 150 caracteres.
- "cierre": una frase final corta que anime a mirar o compartir. Máximo 90 caracteres.

Reglas:
- Español de España, de tú, a una sola persona. Puedes usar 1 o 2 emojis.
- Lenguaje neutro en género: nada de «listo», «aburrido», «aventurero», «chicos».
- No empieces con «¡Hola!», «¡Oye!» ni «¿Te apetece vivir una aventura…?». Sé original.
- Que el gancho venga a cuento del contexto, no una frase genérica sobre Erasmus+.
- NO des ningún dato: ni cifras, ni fechas, ni nombres de proyectos, ni datos sobre países
  o ciudades, ni requisitos, ni precios. Los datos ya van en el bloque.
- No digas que es un mensaje automático ni semanal, ni hables de «temas».
- Devuelve JSON: {{"gancho": "...", "cierre": "..."}}
"""


def _tidy(text: str) -> str:
    """Quita la «!» suelta que a veces queda tras un emoji final («✨!»)."""
    return re.sub(r"(?<=[^\w\s¡!¿?.,;:])!+$", "", text.strip()).strip()


def validate_line(text: str, max_len: int) -> str | None:
    text = (text or "").strip()
    if not text:
        return "vacío"
    if len(text) > max_len:
        return "demasiado largo"
    if re.search(r"\d", text):
        return "lleva cifras"
    if _BANNED.search(text):
        return "lleva una palabra vetada"
    return None


async def write_hook(theme: str, context: str, rng: random.Random, attempts: int = 2) -> tuple[str, str]:
    """(gancho, cierre). Nunca falla: si la IA no da algo válido, usa los de reserva."""
    fallback = (rng.choice(FALLBACK_HOOKS[theme]), rng.choice(FALLBACK_CLOSINGS))
    if cfg.llm_provider == "fake":
        return fallback
    try:
        from google.genai import types

        from app.llm import chat as chat_llm
        from app.llm.retry import with_retry

        if not (await chat_llm.status())["disponible"]:
            return fallback
        for _ in range(attempts):
            response = with_retry(
                lambda: chat_llm._gemini_client().models.generate_content(
                    model=cfg.llm_model,
                    contents=build_prompt(theme, context, rng),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=1.0, max_output_tokens=300,
                    ),
                ),
                attempts=2,
            )
            await chat_llm._record_usage(response)
            try:
                data = json.loads(chat_llm._strip_fences(response.text))
                hook, closing = str(data.get("gancho") or "").strip(), str(data.get("cierre") or "").strip()
            except (ValueError, AttributeError):
                continue
            hook, closing = _tidy(hook), _tidy(closing)
            problem = validate_line(hook, 150) or validate_line(closing, 90)
            if not problem:
                return hook, closing
            log.warning("Gancho %s descartado (%s): %r / %r", theme, problem, hook, closing)
    except Exception:  # noqa: BLE001 - la IA es un extra; el mensaje sale igual
        log.warning("IA no disponible para el gancho %s; uso el de reserva", theme, exc_info=True)
    return fallback


# ---------------------------------------------------------------- montaje y formatos

def compose(hook: str, body: str, closing: str) -> str:
    parts = [hook, body, closing]
    if cfg.map_public_url:
        parts[-1] = f"{closing}\n🗺️ [Todas las oportunidades en el mapa]({cfg.map_public_url})"
    return "\n\n".join(p for p in parts if p)


def to_telegram_html(text: str) -> str:
    out = html.escape(text, quote=False)
    out = _LINK.sub(lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', out)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out, flags=re.S)


def to_whatsapp(text: str) -> str:
    def link(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        bare = re.sub(r"^https?://", "", url).rstrip("/")
        return url if label.strip().rstrip("/") in (url, bare) else f"{label}: {url}"

    # «**[título](url)**»: la negrita de WhatsApp no debe envolver la URL.
    out = re.sub(r"\*\*\[([^\]]+)\]\((https?://[^)\s]+)\)\*\*", r"*\1*: \2", text)
    out = _LINK.sub(link, out)
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", out, flags=re.S)


_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def fits(text: str) -> bool:
    return pub._visible_len(to_telegram_html(text)) <= _MAX_VISIBLE
