"""Piloto automático de Instagram: planifica, genera, publica, mide y aprende. Sin humanos.

Feed (una pieza al día; la hora exacta la decide el experimento):
    lunes a jueves y sábado  carrusel de la oportunidad más vista de la semana que aún no
                             haya salido en el feed (si no hay vistas, la mejor valorada)
    viernes                  carrusel «Última llamada» + Reel «Última llamada»
    domingo                  carrusel «La semana en Corradi» (nuevas, abiertas, más vistas)
Además, cada oportunidad que se publica sale al momento como story y como Reel (este solo
en la pestaña de Reels, no en la cuadrícula). Lo lanza `pipeline` al publicarse.

Cada ejecución (cron cada 30 min): planifica el día si no lo está, publica lo que toque,
y una vez al día refresca métricas y guarda los seguidores. Los lunes manda un informe.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from app.config import cfg
from app.db.pool import get_pool
from app.ig_auto import content as C
from app.ig_auto import design as D
from app.ig_auto import graph, learn, video
from app.publisher import instagram as ig

log = logging.getLogger("corradi.ig_auto")

CALENDAR: dict[int, list[str]] = {
    0: ["carousel_opp"], 1: ["carousel_opp"], 2: ["carousel_opp"], 3: ["carousel_opp"],
    4: ["lastcall", "reel_lastcall"], 5: ["carousel_opp"], 6: ["summary"],
}
SLOT_PREDICATE = "kind NOT IN ('reel_project', 'pinned_intro')"
LOCK_ID = 2026111301
MAX_ATTEMPTS = 3
LATE_LIMIT = timedelta(hours=8)     # si el cron estuvo caído más de esto, se salta el hueco
SCORE_AFTER = timedelta(days=3)     # la puntuación se fija a los 3 días de publicarse


def tz() -> ZoneInfo:
    return ZoneInfo(cfg.timezone)


# ───────────────────────────── base de datos ─────────────────────────────

async def _q(sql: str, params: tuple = (), fetch: bool = True) -> list[dict[str, Any]]:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            return list(await cur.fetchall()) if fetch and cur.description else []


async def history(days: int = 120) -> list[dict[str, Any]]:
    return await _q("SELECT * FROM ig_autopilot WHERE created > now() - %s::interval ORDER BY planned_at",
                    (f"{days} days",))


async def open_rows(today: date) -> list[dict[str, Any]]:
    return await _q("SELECT * FROM projects WHERE status='open' "
                    "AND (application_deadline IS NULL OR application_deadline >= %s)", (today,))


async def views_by_project(days: int = 30) -> dict[Any, int]:
    try:
        rows = await _q("SELECT project_id, SUM(count)::int n FROM project_interactions "
                        "WHERE kind='view' AND day >= current_date - %s GROUP BY project_id", (days,))
    except Exception:  # noqa: BLE001 - tabla opcional
        return {}
    return {r["project_id"]: r["n"] for r in rows}


# ───────────────────────────── planificación ─────────────────────────────

async def plan_day(day: date, rng: random.Random | None = None) -> list[dict[str, Any]]:
    rng = rng or random.Random()
    hist = await history()
    planned = []
    for kind in CALENDAR[day.weekday()]:
        variant = learn.choose(kind, hist, rng)
        minute = rng.randint(0, 40)
        at = datetime.combine(day, time(variant["hour"], minute), tz())
        rows = await _q(
            "INSERT INTO ig_autopilot (kind, slot_date, planned_at, variant) VALUES (%s, %s, %s, %s::jsonb) "
            f"ON CONFLICT (kind, slot_date) WHERE {SLOT_PREDICATE} DO NOTHING RETURNING *",
            (kind, day, at, json.dumps(variant)),
        )
        planned += rows
    return planned


async def due(now: datetime) -> list[dict[str, Any]]:
    return await _q("SELECT * FROM ig_autopilot WHERE status='planned' AND planned_at <= %s "
                    "AND attempts < %s ORDER BY planned_at", (now, MAX_ATTEMPTS))


async def _finish(row_id: int, **fields) -> None:
    sets = ", ".join(f"{k} = %s::jsonb" if k in ("metrics", "variant") else f"{k} = %s" for k in fields)
    await _q(f"UPDATE ig_autopilot SET {sets} WHERE id = %s", (*fields.values(), row_id), fetch=False)


# ───────────────────────────── generación ─────────────────────────────

def _photo(opp: dict[str, Any], size):
    from app.publisher.instagram_card import _project_photo
    try:
        return _project_photo(opp, size)
    except Exception:  # noqa: BLE001
        return None


async def _featured(today: date, hist: list[dict[str, Any]]) -> dict[str, Any] | None:
    """La más vista de la semana que no haya salido en el feed en 60 días."""
    since = today - timedelta(days=60)
    used = {h["project_id"] for h in hist if h.get("project_id") and h["slot_date"] >= since
            and h["kind"] in ("carousel_opp", "reel_opp") and h["status"] in ("published", "planned")}
    return C.pick_most_viewed(await open_rows(today), today, used, await views_by_project(7),
                              await views_by_project(30))


def _cta(rng: random.Random) -> str:
    return rng.choice(C.CTAS)


async def build(row: dict[str, Any], today: date, rng: random.Random) -> dict[str, Any] | None:
    """Genera los ficheros y el texto. Devuelve {'type', 'urls'|'video', 'caption', ...} o None si
    hoy no hay contenido para ese hueco."""
    kind, variant = row["kind"], dict(row["variant"] or {})
    hist = await history()
    if kind in ("carousel_opp", "reel_opp"):
        opp = await _featured(today, hist)
        if not opp:
            return None
        hook = C.hook(opp, variant.get("hook", "afirmacion"))
        variant["country"] = opp["country_code"]
        caption = C.caption_opportunity(opp, hook, _cta(rng))
        deadline_big = C.short_date(opp["application_deadline"])
        if kind == "carousel_opp":
            photo = await asyncio.to_thread(_photo, opp, D.FEED)
            badge = C.week_badge(opp["id"], await open_rows(today), await views_by_project(7))
            slides = [
                D.cover(photo, hook, opp["type"], badge),
                D.details_visual(opp, photo, C.stats(opp), C.summary(opp)),
                D.apply_slide(deadline_big, C.apply_steps(opp), "Guárdalo y etiqueta a tu +1"),
            ]
            return {"type": "carousel", "urls": [graph.save_image(s) for s in slides], "caption": caption,
                    "project_id": opp["id"], "variant": variant}
        path, url = graph.video_path(hashlib.md5(f"{row['id']}-{opp['id']}".encode()).hexdigest()[:16])
        photo = await asyncio.to_thread(_photo, opp, D.STORY)
        cover_s = await asyncio.to_thread(
            video.reel_opportunity, photo, hook, C.stats(opp), C.summary(opp)[:160], deadline_big, path,
            variant.get("music", "house"), rng.randint(0, 10**6),
        )
        return {"type": "reel", "video": url, "cover_ms": round(cover_s * 1000), "caption": caption,
                "project_id": opp["id"], "variant": variant}

    if kind == "summary":
        rows = await open_rows(today)
        items = C.summary_items(rows, today, await views_by_project(7))
        if len(items) < 3:
            return None
        new_count = (await _q("SELECT count(*)::int n FROM projects WHERE published_telegram "
                              "AND created >= now() - interval '7 days'"))[0]["n"]
        start = today - timedelta(days=6)
        label = f"{start.day} {C.MES[start.month - 1]} – {today.day} {C.MES[today.month - 1]}"
        photos = [await asyncio.to_thread(_photo, i["row"], D.FEED) for i in items]
        total = len(items) + 2
        slides = [D.summary_cover_v2(photos, label, len(items))]
        for n, (it, ph) in enumerate(zip(items, photos), 1):
            slides.append(D.summary_slide(ph, n, C.hook(it["row"], "afirmacion"), it["title"], it["type"],
                                          it["closes"], f"{n + 1}/{total}"))
        slides.append(D.summary_closing(new_count, len(rows), f"{total}/{total}"))
        return {"type": "carousel", "urls": [graph.save_image(s) for s in slides],
                "caption": C.caption_summary(items, new_count, _cta(rng)), "variant": variant}

    if kind == "guide":
        used = [h["ref"] for h in hist if h["kind"] == "guide" and h.get("ref") and h["status"] == "published"]
        guide = min(C.GUIDES, key=lambda g: (used.count(g["key"]), max(
            [i for i, k in enumerate(used) if k == g["key"]], default=-1)))
        bg = variant.get("bg", "sage")
        slides = [
            D.guide_cover(guide["kicker"], guide["lines"], guide["hl"], guide["sub"], bg),
            D.guide_cards(guide["heading"], guide["cards"], guide["footnote"], "2/3"),
            D.guide_closing(guide["close_kicker"], guide["close_lines"], guide["close_hl"], guide["close_sub"],
                            "Guárdalo para cuando lo necesites", "3/3"),
        ]
        caption = f"{guide['caption']}\n\n{_cta(rng)}\n\n👉 Oportunidades abiertas: link en la bio.\n\n{C.BASE_TAGS}"
        return {"type": "carousel", "urls": [graph.save_image(s) for s in slides], "caption": caption,
                "ref": guide["key"], "variant": variant}

    if kind in ("lastcall", "reel_lastcall"):
        items = C.lastcall_items(await open_rows(today), today)
        if len(items) < 2:
            return None
        caption = C.caption_lastcall(items, _cta(rng))
        if kind == "lastcall":
            slides = [D.lastcall_cover(len(items), [i["country_code"] for i in items], variant.get("bg", "clay"))]
            for n in range(0, len(items), 5):
                slides.append(D.lastcall_list(items[n:n + 5], f"{len(slides) + 1}/{1 + (len(items) + 4) // 5}"))
            return {"type": "carousel", "urls": [graph.save_image(s) for s in slides], "caption": caption,
                    "variant": variant}
        path, url = graph.video_path(hashlib.md5(f"{row['id']}-lastcall".encode()).hexdigest()[:16])
        cover_s = await asyncio.to_thread(video.reel_lastcall, items, path, variant.get("music", "house"),
                                          rng.randint(0, 10**6), variant.get("bg", "clay"))
        return {"type": "reel", "video": url, "cover_ms": round(cover_s * 1000), "caption": caption,
                "variant": variant}
    raise ValueError(kind)


async def publish(built: dict[str, Any]) -> tuple[str, str | None]:
    if built["type"] == "carousel":
        return await graph.publish_carousel(built["urls"], built["caption"])
    return await graph.publish_reel(built["video"], built["caption"], built["cover_ms"])


async def run_due(now: datetime | None = None, dry_run: bool = False) -> list[str]:
    now = now or datetime.now(tz())
    done = []
    for row in await due(now):
        if now - row["planned_at"] > LATE_LIMIT:
            await _finish(row["id"], status="skipped", error="hueco perdido (cron caído)")
            continue
        rng = random.Random(row["id"])
        try:
            built = await build(row, now.date(), rng)
            if not built:
                await _finish(row["id"], status="skipped", error="sin contenido para este hueco")
                continue
            if dry_run:
                done.append(f"{row['kind']}: {built.get('urls') or built.get('video')}")
                continue
            media_id, permalink = await publish(built)
            await _finish(row["id"], status="published", media_id=media_id, permalink=permalink,
                          published_at=datetime.now(tz()), project_id=built.get("project_id"),
                          ref=built.get("ref"), variant=json.dumps(built["variant"]), error=None)
            done.append(f"{row['kind']} → {permalink or media_id}")
            log.info("Publicado %s: %s", row["kind"], permalink or media_id)
        except ig.InstagramTokenExpired:
            from app import instagram_auth
            await instagram_auth.notify_expired()
            break
        except Exception as e:  # noqa: BLE001
            log.exception("Falló %s", row["kind"])
            attempts = row["attempts"] + 1
            await _finish(row["id"], attempts=attempts, error=f"{type(e).__name__}: {e}"[:1500],
                          status="failed" if attempts >= MAX_ATTEMPTS else "planned",
                          planned_at=now + timedelta(minutes=45))
    return done


# ───────────────────────────── métricas e informe ─────────────────────────────

async def refresh_metrics() -> int:
    rows = await _q("SELECT * FROM ig_autopilot WHERE status='published' AND media_id IS NOT NULL "
                    "AND published_at > now() - interval '30 days' "
                    "AND (metrics_at IS NULL OR metrics_at < now() - interval '20 hours')")
    n = 0
    for r in rows:
        try:
            m = await graph.media_metrics(r["media_id"])
        except Exception as e:  # noqa: BLE001
            log.warning("Sin métricas para %s: %s", r["media_id"], e)
            continue
        old_enough = datetime.now(tz()) - r["published_at"] >= SCORE_AFTER
        await _finish(r["id"], metrics=json.dumps(m), metrics_at=datetime.now(tz()),
                      score=learn.score(m) if old_enough else None)
        n += 1
    try:
        acc = await graph.account()
        await _q("INSERT INTO ig_account_daily (day, followers, media) VALUES (%s, %s, %s) "
                 "ON CONFLICT (day) DO UPDATE SET followers = EXCLUDED.followers, media = EXCLUDED.media",
                 (datetime.now(tz()).date(), acc.get("followers_count") or 0, acc.get("media_count")), fetch=False)
    except Exception as e:  # noqa: BLE001
        log.warning("Sin datos de la cuenta: %s", e)
    return n


async def report() -> str:
    today = datetime.now(tz()).date()
    rows = await _q("SELECT * FROM ig_autopilot WHERE slot_date > %s - 7 AND slot_date <= %s ORDER BY planned_at",
                    (today, today))
    acc = await _q("SELECT * FROM ig_account_daily WHERE day >= %s - 8 ORDER BY day", (today,))
    lines = ["📈 <b>Instagram · semana</b>"]
    if acc:
        delta = acc[-1]["followers"] - acc[0]["followers"]
        lines.append(f"Seguidores: {acc[-1]['followers']} ({'+' if delta >= 0 else ''}{delta} en {len(acc) - 1} días)")
    lines.append("")
    for r in rows:
        m = r.get("metrics") or {}
        stat = (f"alcance {m.get('reach', '–')} · guardados {m.get('saved', '–')} · compartidos {m.get('shares', '–')}"
                if m else r["status"])
        v = ", ".join(f"{k}={val}" for k, val in (r.get("variant") or {}).items() if k != "country")
        lines.append(f"• {r['slot_date']:%a %d} {r['kind']} [{v}] → {stat}")
    learned = learn.summary(await history())
    if learned:
        lines += ["", "<b>Lo aprendido</b>"] + [f"• {x}" for x in learned]
    return "\n".join(lines)


async def send_report() -> None:
    from app.publisher import telegram_publisher as pub
    target = cfg.instagram_alert_telegram_id or (cfg.admin_telegram_ids[0] if cfg.admin_telegram_ids else None)
    if target:
        await pub.send_chunked_dm(target, await report())


async def reel_for_opportunity(opp: dict[str, Any]) -> str | None:
    """Reel de una oportunidad recién publicada (solo pestaña de Reels). Prueba gancho y
    música como variantes y queda registrado para medirlo."""
    if not (opp.get("country_code") and days_or_none(opp)):
        log.info("Sin Reel para %s: faltan fechas o país", opp.get("identifier"))
        return None
    rng = random.Random()
    variant = learn.choose("reel_project", await history(), rng)
    hook = C.hook(opp, variant["hook"])
    dl = opp.get("application_deadline")
    path, url = graph.video_path(hashlib.md5(f"p-{opp['id']}".encode()).hexdigest()[:16])
    photo = await asyncio.to_thread(_photo, opp, D.STORY)
    cover_s = await asyncio.to_thread(
        video.reel_opportunity, photo, hook, C.stats(opp), C.summary(opp)[:160],
        C.short_date(dl) if dl else "Abierta", path, variant["music"], rng.randint(0, 10**6),
    )
    media_id, permalink = await graph.publish_reel(url, C.caption_opportunity(opp, hook, _cta(rng)),
                                                   round(cover_s * 1000), share_to_feed=False)
    now = datetime.now(tz())
    await _q("INSERT INTO ig_autopilot (kind, slot_date, planned_at, project_id, variant, status, media_id, "
             "permalink, published_at) VALUES ('reel_project', %s, %s, %s, %s::jsonb, 'published', %s, %s, %s)",
             (now.date(), now, opp["id"], json.dumps(variant), media_id, permalink, now), fetch=False)
    return media_id


def days_or_none(opp: dict[str, Any]) -> int | None:
    return C.days(opp)


async def story_for_opportunity(opp: dict[str, Any]) -> str:
    """Story de una oportunidad nueva con el diseño del piloto. La usa `instagram.publish_story`."""
    hook = C.hook(opp, "afirmacion")
    dl = opp.get("application_deadline")
    pill = f"PLAZO {C.short_date(dl).upper()}" if dl else "INSCRIPCIÓN ABIERTA"
    jpeg = D.story(await asyncio.to_thread(_photo, opp, D.STORY), hook, opp.get("type") or "", pill)
    return graph.save_image(jpeg)
