# Piloto automático de Instagram

Desde el 13 de noviembre de 2026 la cuenta @corradierasmus funciona sola. Nadie revisa ni aprueba nada. El código está en `app/ig_auto/` y se lanza desde `app/scheduler/ig_autopilot.py`.

## Qué publica

**Cada oportunidad que se publica en el canal** sale al momento en Instagram como **story** y como **Reel**. El Reel va solo a la pestaña de Reels, no a la cuadrícula. Los lanza `pipeline` (`autopilot.story_for_opportunity` y `autopilot.reel_for_opportunity`).

**Feed: una pieza al día** (decidido con el usuario el 13-nov-2026):

| Día | Pieza |
|---|---|
| Lunes a jueves y sábado | Carrusel de la **oportunidad más vista de la semana** que no haya salido en el feed en 60 días; si no hay vistas, la mejor valorada (`content.pick_most_viewed`) |
| Viernes | Última llamada: carrusel + Reel con las YE/TC que cierran en 7 días |
| Domingo | Carrusel «La semana en Corradi»: nuevas, abiertas y las 5 más vistas |

**Las guías** (`content.GUIDES`) quedaron fuera del calendario porque el usuario no quiere repetir lo mismo cada semana. El código sigue ahí por si se usan de forma puntual.

Para volver al modo antiguo (post de feed + story + Reel por oportunidad con el diseño viejo), pon `IG_FEED_PER_OPPORTUNITY=1`.

## Reglas que no hay que romper (no hay revisión humana)

- **En las imágenes solo van datos estructurados:** tipo, país, ciudad, fechas, duración calculada de las fechas, plazo, plazas y edades. Nada sacado de texto libre de la IA en portadas, como «todo cubierto».
- **Destacadas:** abiertas, con plazo a 3 días o más, que admiten residentes en España y con fechas. No se repite oportunidad en el feed en 60 días.
- **Las guías usan solo datos estables del programa** escritos en `content.GUIDES`. No añadas cifras sin comprobarlas en la Guía del Programa.
- **Música:** generada por código en `music.py`, en 6 estilos (house, lofi, afro, dembow, synthpop, indie). No se descarga nada, así que no hay problemas de derechos.
- **No hacer:** anuncios de pago, seguir o dejar de seguir en masa, mensajes directos, ni prometer nada que no esté en la ficha.

## Cómo aprende

- **Variantes:** cada hueco del calendario elige una combinación según `learn.DIMENSIONS`: tipo de gancho (afirmación o pregunta), hora, fondo y estilo de música.
- **Métricas:** cada día a las 8:15 se refrescan (alcance, guardados, compartidos, me gusta, comentarios, vistas) y se guardan los seguidores en `ig_account_daily`.
- **Puntuación:** a los 3 días de publicarse se fija la puntuación de cada pieza (`learn.score`), que premia guardados y compartidos por cuenta alcanzada.
- **Decisión:** epsilon-greedy. Primero prueba cada variante al menos 2 veces; después usa la mejor el 70 % de las veces y explora el 30 % restante.
- **Informe:** los lunes a las 9:30 llega por Telegram a `INSTAGRAM_ALERT_TELEGRAM_ID`, o al primer admin si no está configurado.

## Ficheros públicos

Para no tocar `main.py`, se reutilizan dos rutas que ya existen:
- **Imágenes JPEG** en `MEDIA_DIR/opportunities/<md5>.jpg`, servidas en `/media/opportunities/<md5>.jpg`.
- **Vídeos** en `MEDIA_DIR/reels/CORRADI-AUTO-<hex>.mp4`, servidos en `/ig/CORRADI-AUTO-<hex>/reel.mp4`.

## Cron (EC2, TZ Europe/Madrid)

```
*/30 9-23 * * * cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.ig_autopilot >> /tmp/corradi_ig_autopilot.log 2>&1
15 8 * * *      cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.ig_autopilot --metrics >> /tmp/corradi_ig_autopilot.log 2>&1
30 9 * * 1      cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.ig_autopilot --report >> /tmp/corradi_ig_autopilot.log 2>&1
```

El barrido antiguo `publish_instagram` (cada 2 h) sigue activo: reintenta las stories de oportunidades que fallaron.

## Revisión periódica (cuando alguien abra una sesión)

1. **Mirar** `SELECT kind, slot_date, status, variant, metrics, score, error FROM ig_autopilot ORDER BY planned_at DESC LIMIT 40;` y la evolución de `ig_account_daily`.
2. **Errores:** ver `/tmp/corradi_ig_autopilot.log` y las filas con `status='failed'`.
3. **Decidir con los datos:**
   - quitar variantes que pierden claramente en `learn.DIMENSIONS`
   - añadir variantes nuevas (gancho, diseño, música)
   - cambiar el calendario en `autopilot.CALENDAR`
   - escribir guías nuevas
4. **Probar sin publicar:** `python -m app.scheduler.ig_autopilot --dry-run`.

## Lo que la API no permite (fijo)

Hasta donde sabemos, la API de publicación no permite cambiar la bio, la foto ni los destacados, fijar o quitar publicaciones fijadas, borrar o archivar posts, editar textos publicados, añadir pegatinas (enlace, encuesta, cuenta atrás) ni música de la biblioteca de Instagram. Todo eso se queda como está.
