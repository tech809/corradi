# Publicación automática en Instagram

Cada vez que una oportunidad se publica de verdad en el canal de Telegram
(`pipeline.commit()`), se publica también en Instagram: un post de feed (1080×1350) y una
story a juego (1080×1920), con el mismo sistema de color por categoría que ya usan el mapa
y el canal (azul Youth Exchange, ámbar Training Course, verde ECS).

Vacío (`INSTAGRAM_LONG_LIVED_TOKEN` sin poner) = desactivado sin más, el resto del pipeline
sigue exactamente igual. No hace falta nada para probar el resto del sistema sin tener la
cuenta de Instagram lista todavía.

## Por qué esta arquitectura y no la de tur-app

`tur-app/ig-automation` (que ya conocéis y funciona) publica desde **GitHub Actions**, con
la cola en un `queue.json` versionado en git y las imágenes alojadas en un repo público
aparte (`raw.githubusercontent.com`). Tiene sentido ahí: tur-app no tiene servidor propio.

Corradi sí lo tiene (EC2 24/7, Postgres, API con dominio público), así que aquí es distinto:

| | tur-app | Corradi |
|---|---|---|
| Cola | `content/queue.json` en git | tabla `instagram_posts` (Postgres) |
| Imágenes | repo público aparte en GitHub | `GET /ig/{id}/post.png` y `/story.png`, la misma API que ya sirve el mapa |
| Quién publica | GitHub Actions, cron diario fijo | el propio `pipeline.commit()` al instante + cron cada 2h de red de seguridad |
| Caption | escrito a mano (contenido editorial) | generado del todo por plantilla — cero pasos manuales |
| Renovar el token | manual (README lo marca como pendiente) | cron semanal en el mismo EC2, sin gymnastics de secrets de GitHub |

## Cómo funciona

1. `pipeline.commit()` publica en Telegram (como siempre) y, si sale bien, encola la
   oportunidad en `instagram_posts` (`status='pending'`) **e intenta publicarla ya mismo**
   si Instagram está configurado. Un fallo aquí nunca afecta a Telegram — ya se publicó.
2. `app/scheduler/publish_instagram.py`, por cron cada 2 horas, recoge lo que siga
   `pending` o `failed` (sin agotar los reintentos) y lo publica — es la red de seguridad
   para lo que falló al instante (token caducado, un pico de la API, etc.). Sin tope diario
   de publicaciones; prioriza lo que cierra antes.
3. Las imágenes las genera `app/publisher/instagram_card.py` (Pillow, reutiliza la paleta
   de `opportunity_card.py`) y las sirve `app/api/main.py` bajo demanda — Instagram las
   descarga de esa URL pública al crear cada contenedor de media.
4. El caption (`app/publisher/instagram.py::build_caption`) sale entero de los datos ya
   extraídos: título, lugar, fechas, plazo con la misma cuenta atrás que el canal/mapa
   ("quedan 3 días"), CTA fijo ("link en bio" — Instagram no permite enlaces en el pie) y
   hashtags por categoría.
5. Además del feed+story, en cuanto esos dos se publican bien se lanza en segundo plano
   (sin bloquear la respuesta) la generación y publicación de un **Reel** (2026-07-28):
   mismo fondo/diseño que el post, pero animado (zoom-out + aparición escalonada de cada
   bloque de texto) con un fondo musical — ver `app/publisher/reel_video.py` (fotogramas
   con Pillow + codificación con `ffmpeg`, necesita el paquete `ffmpeg` instalado en el
   contenedor `bot`) y `app/publisher/reel_audio.py` (la música es **100% sintetizada en
   Python puro**, no descargada de ningún sitio — así no hay ninguna duda de derechos de
   autor sobre una pista de terceros en una cuenta pública). El .mp4 se genera en `bot` y
   se deja en el volumen compartido `media_data` (`MEDIA_DIR`, montado también en `api`),
   que lo sirve tal cual por `GET /ig/{id}/reel.mp4` — nada de generarlo al vuelo en esa
   ruta pública, sería demasiado lento. El Reel **no** tiene cola de reintentos propia
   (a diferencia de feed/story): si falla, se registra en los logs y ya, porque para
   entonces lo importante (feed y story) ya se ha publicado.

## Puesta en marcha (la parte manual)

1. **Crear la cuenta de Instagram** y pasarla a **Business** o **Creator**
   (Ajustes → Cuenta → Cambiar a cuenta profesional).
2. **Crear/usar una Página de Facebook** y vincularla a la cuenta de Instagram (Meta exige
   una Página de Facebook detrás de toda cuenta de IG gestionada por la Graph API, aunque
   nunca se use para nada más).
3. En [developers.facebook.com](https://developers.facebook.com), crear una app tipo
   **Business**, añadir el producto **Instagram** y generar un token con los permisos
   `instagram_business_content_publish` + `instagram_business_basic` (y
   `pages_show_list`/`pages_read_engagement` para poder listar la Página vinculada).
4. Sacar el `INSTAGRAM_BUSINESS_ACCOUNT_ID` (el id de la cuenta de IG, no el de la Página) —
   vía el explorador de la Graph API o `GET /me/accounts` seguido de
   `GET /{page_id}?fields=instagram_business_account`.
5. El "Generate token" del dashboard de la app ya da un token de **larga duración (60
   días)** — igual que en tur-app, **no** pasarlo por `ig_exchange_token` (eso da el 452
   "Session key invalid" que ya os pasó con tur-app).
6. Poner en `.env` (o en el `.env` del EC2): `INSTAGRAM_LONG_LIVED_TOKEN`,
   `INSTAGRAM_BUSINESS_ACCOUNT_ID`, `INSTAGRAM_IMAGE_BASE_URL=https://mapa.proactivefuture.eu`.
7. `docker exec -i corradi-db psql -U corradi -d corradi < db/migrations/0009_instagram.sql`
   (crea la tabla de cola — solo hace falta una vez).
8. Reconstruir `api` y `bot`, y añadir el cron cada 2h (ver más abajo).

Sin renovación automática del token todavía (igual que tur-app la tiene pendiente) — toca
renovarlo a mano antes de los 60 días con `ig_refresh_token`. Si hace falta, lo automatizamos
después con un cron semanal en el propio EC2 (no hay el problema de secrets de GitHub Actions
que tiene tur-app, así que aquí sería más simple).

## Cron (EC2, añadir junto a los que ya hay)

```
0 */2 * * * cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.publish_instagram >> /tmp/corradi_instagram.log 2>&1
```

## Probar sin publicar de verdad

Generar la imagen y el caption tal cual saldrían, sin llamar a la Graph API:

```python
from app.db import repository as repo
from app.db.pool import open_pool, close_pool
from app.publisher import instagram, instagram_card
import asyncio

async def preview(identifier):
    await open_pool()
    opp = await repo.get_by_identifier(identifier)
    await close_pool()
    label = instagram.days_left_label(opp)
    print(instagram.build_caption(opp))
    open("/tmp/feed.png", "wb").write(instagram_card.render_feed(opp, label))
    open("/tmp/story.png", "wb").write(instagram_card.render_story(opp, label))

asyncio.run(preview("CORRADI-2026-0035"))
```

Para ver la imagen tal cual la vería Instagram (ya con fuentes reales, no el fallback local),
lo más fiable es `GET https://mapa.proactivefuture.eu/ig/{identifier}/post.png` directamente
una vez desplegado.

## Decisiones pendientes / a revisar con el uso real

- **Formato**: feed 4:5 (1080×1350) + story 9:16. Si se prefiere cuadrado (1:1) para la
  parrilla del perfil, es un solo número en `instagram_card.FEED_SIZE`.
- **Caption 100% plantilla**: sin paso de reescritura por LLM. Si algún día se quiere un
  toque más editorial, es un único punto de extensión en `build_caption()`.
- **Sin tope diario**: cada oportunidad publicada en Telegram genera su post de Instagram,
  sin límite — a valorar si con más volumen conviene limitar publicaciones/día.
