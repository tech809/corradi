"""Qué se publica y con qué textos. Solo datos fiables de la ficha.

Regla de oro (no hay nadie revisando antes de publicar): en las imágenes solo aparecen
datos estructurados y comprobables: tipo, país, ciudad, fechas, duración calculada de las
fechas, plazo, plazas y edades. Nada sacado de texto libre de la IA (como «todo cubierto»)
va en una portada. Las guías usan solo datos estables del programa escritos aquí.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.publisher import telegram_publisher as pub

MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
TYPE_TITLE = {"YOUTH_EXCHANGE": "Youth Exchange", "TRAINING_COURSE": "Training Course",
              "VOLUNTEERING": "Voluntariado ESC"}
_EXTRA_COUNTRIES = {
    "EG": "Egipto", "AM": "Armenia", "GE": "Georgia", "AZ": "Azerbaiyán", "UA": "Ucrania", "MD": "Moldavia",
    "AL": "Albania", "MK": "Macedonia del Norte", "XK": "Kosovo", "BA": "Bosnia", "ME": "Montenegro",
    "RS": "Serbia", "TN": "Túnez", "MA": "Marruecos", "JO": "Jordania", "LB": "Líbano", "TR": "Turquía",
    "IS": "Islandia", "NO": "Noruega", "LI": "Liechtenstein", "CH": "Suiza", "GB": "Reino Unido",
}


# ───────────────────────────── utilidades de datos ─────────────────────────────

def _d(v) -> date | None:
    if v is None or isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def country(code: str | None) -> str:
    code = (code or "").upper()
    name = pub._PAISES_ES.get(code) or _EXTRA_COUNTRIES.get(code) or ""
    return re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", name)


def city(opp: dict[str, Any]) -> str:
    c = (opp.get("location") or "").split(",")[0].strip()
    if c.lower() in (country(opp.get("country_code")).lower(), (opp.get("country_code") or "").lower()):
        return ""
    return c


def days(opp: dict[str, Any]) -> int | None:
    s, e = _d(opp.get("start_date")), _d(opp.get("end_date"))
    if s and e and e >= s:
        return (e - s).days + 1
    return None


def plausible_days(opp: dict[str, Any]) -> int | None:
    """Duración solo si es creíble: un Youth Exchange o Training Course de más de 30 días casi
    siempre es una fecha mal extraída, así que no se usa en ganchos ni cifras."""
    n = days(opp)
    if n and opp.get("type") in ("YOUTH_EXCHANGE", "TRAINING_COURSE") and n > 30:
        return None
    return n


def span(n: int) -> str:
    if n > 60:
        m = round(n / 30.4)
        return f"{m} {'mes' if m == 1 else 'meses'}"
    return f"{n} {'día' if n == 1 else 'días'}"


def short_date(v) -> str:
    d = _d(v)
    return f"{d.day} {MES[d.month - 1]}" if d else ""


def long_date(v) -> str:
    d = _d(v)
    return f"{d.day} de {MESES[d.month - 1]}" if d else ""


def dates(opp: dict[str, Any]) -> str:
    s, e = _d(opp.get("start_date")), _d(opp.get("end_date"))
    if not (s and e):
        return ""
    if s.month == e.month and s.year == e.year:
        return f"{s.day}–{e.day} {MES[s.month - 1]}"
    return f"{s.day} {MES[s.month - 1]} – {e.day} {MES[e.month - 1]}"


def looks_spanish(text: str) -> bool:
    t = f" {text.lower()} "
    es = sum(t.count(w) for w in (" de ", " la ", " el ", " y ", " en ", " para ", " con "))
    en = sum(t.count(w) for w in (" the ", " and ", " of ", " for ", " with ", " we "))
    return es > en


# ───────────────────────────── ganchos y diapositivas ─────────────────────────────

HOOK_STYLES = ("afirmacion", "pregunta")


def hook(opp: dict[str, Any], style: str) -> dict[str, Any]:
    """Titular de portada y story. Solo duración (de las fechas), país, tipo y fechas."""
    pais = country(opp.get("country_code")) or "Europa"
    n = plausible_days(opp)
    hl = pais.split()
    sub = " · ".join(x for x in (TYPE_TITLE.get(opp.get("type"), "Erasmus+"), dates(opp), city(opp)) if x)
    if not n:
        return {"lines": ["Erasmus+", f"en {pais}."], "hl": hl, "sub": sub}
    if style == "pregunta":
        return {"lines": ["¿Te vas", f"{span(n)} a", f"{pais}?"], "hl": hl, "sub": sub}
    return {"lines": [span(n), f"en {pais}."], "hl": hl, "sub": sub}


def stats(opp: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    n = plausible_days(opp)
    if n:
        num, unit = span(n).split(" ", 1)
        out.append((num, unit))
    if opp.get("max_participants"):
        out.append((str(opp["max_participants"]), "plazas"))
    lo, hi = opp.get("participant_min_age"), opp.get("participant_max_age")
    if lo and hi:
        out.append((f"{lo}–{hi}", "años"))
    if opp.get("application_deadline"):
        out.append((short_date(opp["application_deadline"]), "plazo"))
    if dates(opp) and len(out) < 3:
        out.insert(1, (dates(opp), "fechas"))
    return out[:3]


def summary(opp: dict[str, Any]) -> str:
    s = " ".join(str(opp.get("summary") or "").split())
    if s and looks_spanish(s):
        return s
    topic = " ".join(str(opp.get("topic") or "").split())
    return f"Temas: {topic}." if topic else "Toda la información, fechas y formulario en la ficha."


def apply_steps(opp: dict[str, Any]) -> list[str]:
    title = re.split(r"[–—:|-]", str(opp.get("title") or ""), maxsplit=1)[0].strip()
    if len(title) > 30:
        title = title[:29].rsplit(" ", 1)[0] + "…"
    return ["Abre el link de la bio", f"Busca «{title}» en el mapa", "Lee el infopack y rellena el formulario"]


CTAS = (
    "¿Con quién te irías? Etiquétale 👇",
    "Guárdalo para cuando prepares tu solicitud 🔖",
    "Mándaselo a quien le encantaría ✈️",
    "¿Te lo imaginas? Cuéntanos en comentarios 👇",
)
HASHTAGS = {
    "YOUTH_EXCHANGE": "#YouthExchange #IntercambioJuvenil",
    "TRAINING_COURSE": "#TrainingCourse #FormaciónJuvenil",
    "VOLUNTEERING": "#CuerpoEuropeoDeSolidaridad #VoluntariadoEuropeo",
}
BASE_TAGS = "#ErasmusPlus #Erasmus #JuventudEuropea #ViajarPorEuropa"


def caption_opportunity(opp: dict[str, Any], hook_: dict[str, Any], cta: str) -> str:
    lines = [" ".join(hook_["lines"]), ""]
    flag = pub._flag(opp.get("country_code")) or "🌍"
    lines.append(f"{flag} {opp.get('title')}")
    bits = [x for x in (city(opp), country(opp.get("country_code"))) if x]
    if bits:
        lines.append(f"📍 {', '.join(bits)}")
    if dates(opp):
        lines.append(f"🗓️ {dates(opp)}")
    if opp.get("application_deadline"):
        lines.append(f"⏳ Plazo: {long_date(opp['application_deadline'])}")
    lines += ["", "👉 Toda la info y el formulario: link en la bio (busca el título en el mapa).", "", cta, "",
              f"{HASHTAGS.get(opp.get('type'), '')} {BASE_TAGS}".strip()]
    return "\n".join(lines)


def caption_lastcall(items: list[dict[str, Any]], cta: str) -> str:
    lines = [f"⏰ Última llamada: {len(items)} Erasmus+ que cierran esta semana", ""]
    for it in items[:10]:
        lines.append(f"{pub._flag(it.get('country_code')) or '🌍'} {it['title']} · cierra el {it['closes']}")
    lines += ["", "👉 Todas en el link de la bio.", "", cta, "", BASE_TAGS]
    return "\n".join(lines)


# ───────────────────────────── guías (datos estables del programa) ─────────────────────────────
# Revisadas a mano contra la Guía del Programa Erasmus+ y la del Cuerpo Europeo de Solidaridad.
# No añadir cifras sin comprobarlas.

GUIDES: list[dict[str, Any]] = [
    {
        "key": "que-paga",
        "kicker": "Guía rápida", "lines": ["¿Qué te", "paga", "Erasmus+?"], "hl": ["paga"],
        "sub": "Lo que cubre el programa, explicado fácil",
        "heading": "Youth Exchange y Training Course",
        "cards": [("Viaje", "Un importe según la distancia. Si vas en tren, bus o coche compartido, es mayor."),
                  ("Alojamiento y comidas", "Los organiza el proyecto durante la actividad."),
                  ("Youthpass", "Certificado europeo de lo que aprendes.")],
        "footnote": "Confírmalo siempre en el infopack de cada proyecto.",
        "close_kicker": "Voluntariado ESC", "close_lines": ["Viaje, casa,", "comida, seguro", "y dinero de", "bolsillo."],
        "close_hl": ["bolsillo"], "close_sub": "De 18 a 30 años · de 2 semanas a 12 meses",
        "caption": "¿Qué cubre Erasmus+ cuando te vas de intercambio, de formación o de voluntariado? Te lo contamos en 3 diapositivas.",
    },
    {
        "key": "cual-es-para-ti",
        "kicker": "¿YE, TC o ESC?", "lines": ["¿Cuál es", "para ti?"], "hl": ["ti?"],
        "sub": "Tres formas de irte con Erasmus+ y el Cuerpo Europeo de Solidaridad",
        "heading": "En una frase",
        "cards": [("Youth Exchange", "Grupos de jóvenes de varios países conviven y trabajan un tema. De 13 a 30 años."),
                  ("Training Course", "Formación para quien trabaja con jóvenes: monitores, educadores, voluntarios."),
                  ("Voluntariado ESC", "Colaboras en un proyecto en otro país. De 18 a 30 años.")],
        "footnote": "Cada proyecto marca su perfil exacto en el infopack.",
        "close_kicker": "Duraciones", "close_lines": ["De 5 días", "a 12 meses."], "close_hl": ["12"],
        "close_sub": "Un Youth Exchange dura de 5 a 21 días; un voluntariado ESC, de 2 semanas a 12 meses",
        "caption": "Youth Exchange, Training Course o voluntariado ESC: qué es cada uno y para quién.",
    },
    {
        "key": "como-apuntarte",
        "kicker": "Paso a paso", "lines": ["Cómo", "apuntarte a", "un Erasmus+"], "hl": ["apuntarte"],
        "sub": "Sin líos: de ver la oportunidad a enviar tu solicitud",
        "heading": "Los pasos",
        "cards": [("1 · Elige", "Busca en el mapa por país, fechas o tipo."),
                  ("2 · Lee el infopack", "Fechas, perfil, costes y cómo inscribirte."),
                  ("3 · Rellena el formulario", "El de la organización que envía al grupo desde España."),
                  ("4 · Atento al correo", "La organización te escribe con la respuesta.")],
        "footnote": "",
        "close_kicker": "Consejo", "close_lines": ["No lo dejes", "para el", "último día."], "close_hl": ["último"],
        "close_sub": "Las plazas son limitadas y los plazos, cortos: mira el plazo de cada ficha",
        "caption": "Cómo apuntarte a un Erasmus+ en 4 pasos. Guárdalo para tu próxima solicitud.",
    },
    {
        "key": "infopack",
        "kicker": "Antes de apuntarte", "lines": ["Qué mirar", "en un", "infopack"], "hl": ["infopack"],
        "sub": "El documento con todos los detalles de cada proyecto",
        "heading": "Fíjate en esto",
        "cards": [("Fechas y lugar", "Días de actividad y días de viaje."),
                  ("Perfil", "Edad, país de residencia y a quién buscan."),
                  ("Costes", "Qué se cubre y si hay alguna cuota."),
                  ("Cómo inscribirte", "Formulario, plazo y contacto.")],
        "footnote": "",
        "close_kicker": "En Corradi", "close_lines": ["Cada ficha", "enlaza su", "infopack."], "close_hl": ["infopack."],
        "close_sub": "Y te dice cuántos días quedan para el plazo",
        "caption": "Las 4 cosas que hay que mirar en un infopack antes de apuntarse.",
    },
    {
        "key": "youthpass",
        "kicker": "Para tu CV", "lines": ["¿Qué es", "Youthpass?"], "hl": ["youthpass?"],
        "sub": "El certificado europeo de lo que aprendes",
        "heading": "Lo esencial",
        "cards": [("Qué es", "Un certificado oficial europeo."),
                  ("Cuándo te lo dan", "En Youth Exchanges, Training Courses y voluntariados ESC."),
                  ("Qué recoge", "Lo que has aprendido durante el proyecto.")],
        "footnote": "",
        "close_kicker": "Truco", "close_lines": ["Añádelo", "a tu CV."], "close_hl": ["cv."],
        "close_sub": "Demuestra experiencia internacional y trabajo en equipo",
        "caption": "Youthpass: el certificado europeo que te llevas de un Erasmus+ de juventud.",
    },
    {
        "key": "viaje-verde",
        "kicker": "Viaje sostenible", "lines": ["Ir en tren", "también", "suma."], "hl": ["suma."],
        "sub": "En los proyectos Erasmus+ de juventud, viajar en verde tiene premio",
        "heading": "Cómo funciona",
        "cards": [("Importe según distancia", "El viaje se cubre con una cantidad fija según los kilómetros."),
                  ("Viaje sostenible", "Tren, autobús o coche compartido: el importe es mayor."),
                  ("Pregúntalo", "La organización te explica cómo justificarlo.")],
        "footnote": "Las condiciones exactas van en el infopack.",
        "close_kicker": "Plan", "close_lines": ["Más paisaje,", "menos", "avión."], "close_hl": ["paisaje,"],
        "close_sub": "Y una aventura desde el primer kilómetro",
        "caption": "¿Sabías que viajar en tren o autobús a tu Erasmus+ tiene un importe mayor? Te lo explicamos.",
    },
]


# ───────────────────────────── selección de oportunidades ─────────────────────────────

def eligible_from_spain(opp: dict[str, Any]) -> bool:
    codes = [c.upper() for c in (opp.get("eligibility_country_codes") or [])]
    return "ES" in codes or opp.get("eligibility_scope") == "all_programme"


def featured_score(opp: dict[str, Any], today: date, views: int) -> float:
    quality = sum(bool(opp.get(k)) for k in ("summary", "image_url", "topic", "infopack_url", "application_url"))
    dl = _d(opp.get("application_deadline"))
    urgency = 1 / max(1, (dl - today).days - 6) if dl else 0
    type_bonus = {"YOUTH_EXCHANGE": 1.0, "TRAINING_COURSE": 0.8, "VOLUNTEERING": 0.5}.get(opp.get("type"), 0)
    return quality + 2 * urgency + type_bonus + min(views, 50) / 25


def pick_featured(rows: list[dict[str, Any]], today: date, used_ids: set, recent_countries: list[str],
                  views: dict, min_days: int = 7) -> dict[str, Any] | None:
    cands = []
    for r in rows:
        dl = _d(r.get("application_deadline"))
        if not dl or (dl - today).days < min_days or r["id"] in used_ids:
            continue
        if not (days(r) and r.get("country_code") and eligible_from_spain(r)):
            continue
        cands.append(r)
    if not cands:
        return None
    fresh = [r for r in cands if r["country_code"] not in recent_countries] or cands
    return max(fresh, key=lambda r: featured_score(r, today, views.get(r["id"], 0)))


def pick_most_viewed(rows: list[dict[str, Any]], today: date, used_ids: set, week_views: dict,
                     all_views: dict, min_days: int = 3) -> dict[str, Any] | None:
    """La oportunidad más vista de la semana que aún no ha salido en el feed; si nadie la ha
    visto, la mejor según `featured_score`. Debe tener fechas, país, admitir España y
    quedarle al menos `min_days` de plazo."""
    cands = []
    for r in rows:
        dl = _d(r.get("application_deadline"))
        if not dl or (dl - today).days < min_days or r["id"] in used_ids:
            continue
        if not (days(r) and r.get("country_code") and eligible_from_spain(r)):
            continue
        cands.append(r)
    if not cands:
        return None
    return max(cands, key=lambda r: (week_views.get(r["id"], 0),
                                     featured_score(r, today, all_views.get(r["id"], 0))))


def summary_items(rows: list[dict[str, Any]], today: date, week_views: dict, n: int = 5) -> list[dict[str, Any]]:
    """Las `n` oportunidades abiertas más vistas de la semana (con plazo por delante)."""
    seen = [r for r in rows if week_views.get(r["id"]) and _d(r.get("application_deadline"))
            and _d(r["application_deadline"]) >= today]
    seen.sort(key=lambda r: -week_views[r["id"]])
    return [{"title": r["title"], "type": r.get("type"), "country_code": r.get("country_code"),
             "closes": short_date(r["application_deadline"]), "deadline": _d(r["application_deadline"]),
             "row": r} for r in seen[:n]]


def week_badge(opp_id, rows: list[dict[str, Any]], week_views: dict) -> str | None:
    """Sello de la portada, solo si es verdad según las vistas de la semana."""
    if not week_views.get(opp_id):
        return None
    ranking = sorted((r["id"] for r in rows if week_views.get(r["id"])), key=lambda i: -week_views[i])
    pos = ranking.index(opp_id) + 1 if opp_id in ranking else None
    if pos == 1:
        return "LA MÁS VISTA DE LA SEMANA"
    if pos and pos <= 5:
        return f"TOP {pos} DE LA SEMANA"
    return None


def caption_summary(items: list[dict[str, Any]], new_count: int, cta: str) -> str:
    lines = ["📊 La semana en Corradi", "", f"✨ {new_count} oportunidades nuevas esta semana.", "",
             "Las más vistas:"]
    for it in items:
        lines.append(f"{pub._flag(it.get('country_code')) or '🌍'} {it['title']} · plazo {it['closes']}")
    lines += ["", "👉 Todas en el link de la bio.", "", cta, "", BASE_TAGS]
    return "\n".join(lines)


def lastcall_items(rows: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        dl = _d(r.get("application_deadline"))
        if r.get("type") in ("YOUTH_EXCHANGE", "TRAINING_COURSE") and dl and 0 <= (dl - today).days <= 7 \
                and eligible_from_spain(r):
            out.append({"title": r["title"], "type": r["type"], "country_code": r.get("country_code"),
                        "closes": short_date(dl), "deadline": dl})
    return sorted(out, key=lambda x: x["deadline"])[:10]


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())
