# Opción descartada: publicar como vista previa de enlace (no como foto)

Al diseñar el post del canal con imagen (ver `app/publisher/opportunity_card.py`), se
evaluaron dos formas de publicarlo:

- **Foto adjunta** (`send_photo`) — la elegida, implementada en `pipeline.commit()`.
- **Vista previa de enlace** (`send_message` con un enlace oculto detrás del título,
  apoyada en una página con etiquetas Open Graph) — descartada, mothballed aquí.

La vista previa de enlace daba una imagen y un texto **más anchos** que la foto adjunta
(Telegram limita el ancho de una foto+pie por debajo del de un mensaje de texto, y ese
límite es del cliente, no se puede evitar desde el bot — ver hilos abajo). Se descartó de
todos modos porque el dominio de origen (`mapa.proactivefuture.eu`) sale siempre visible
encima de la tarjeta — es una medida anti-phishing universal en Telegram/Discord/WhatsApp/
iMessage, ninguna etiqueta de la página puede ocultarlo — y quedaba menos limpio que la
foto adjunta.

Se deja documentado por si en el futuro compensa retomarlo (por ejemplo, si el ancho de la
foto llega a doler más que el dominio visible).

## Cómo se montó

1. **Página por oportunidad** — `GET /o/{identifier}`: sirve un HTML con las etiquetas
   `og:image`, `og:image:width/height`, `og:type`, `twitter:card=summary_large_image` y
   `og:site_name`. Sin `og:title` (probado a propósito sin título, Telegram no mostró la
   URL en crudo como alternativa, se veía limpio).

2. **Imagen por oportunidad** — `GET /o/{identifier}/image.png`: la misma función
   `opportunity_card.render()` que usa hoy la foto adjunta.

3. **Enlace oculto en el mensaje**: en vez de pegar la URL en crudo, se envuelve el título
   (u otro texto) en `<a href="...">`, y se manda con
   `link_preview_options=LinkPreviewOptions(url=..., show_above_text=True, prefer_large_media=True)`
   (Bot API 7.0+, `python-telegram-bot` ya lo soporta). `show_above_text=True` es justo el
   parámetro que pone la vista previa ARRIBA del texto en vez de abajo (por defecto).

4. **Identificador reservado de prueba**: `_test_future_shapers`, nunca toca la BD — sirve
   datos hardcodeados en vez de consultar `projects`. Útil para probar sin ensuciar datos
   reales.

## Gotchas encontrados (importantes si se retoma)

- **`<meta http-equiv="refresh">` NO usar para redirigir a humanos** — los rastreadores de
  vista previa (Telegram incluido) lo siguen igual que una redirección HTTP real, y acaban
  leyendo el `og:image` de la página de DESTINO en vez de la original. Usar en su lugar un
  `<script>location.replace(...)</script>` (invisible para un rastreador que no ejecuta
  JS) + un enlace visible de respaldo en el `<body>`.
- **El ratio de la imagen importa para el tratamiento "grande arriba"**: con 1200×630
  (1.91:1, el estándar Open Graph/Twitter) Telegram mostró la imagen grande arriba del
  texto. Con 1200×360 (3.33:1) la mostró pequeña y debajo. No confirmado el punto exacto
  donde cambia el comportamiento.
- **El dominio de origen no se puede ocultar ni sustituir** — ni con `og:site_name` ni de
  ninguna otra forma. Es a propósito, por seguridad (anti-phishing), en todas las
  plataformas grandes de mensajería.
- **Solo se muestra el dominio, no la ruta completa** — aunque la URL real sea
  `https://mapa.proactivefuture.eu/o/CORRADI-2026-0123?v=7`, Telegram solo enseña
  `mapa.proactivefuture.eu`. La ruta no ensucia la vista previa.
- **Caché de Telegram por URL**: si cambias las etiquetas OG de una URL ya compartida
  antes, Telegram puede seguir enseñando la preview vieja — añade un `?v=N` para forzar
  una tarjeta nueva mientras pruebas.

## Fuentes consultadas sobre el ancho de la foto adjunta

- [tdesktop #4992 — Message bubble too narrow with image+caption](https://github.com/telegramdesktop/tdesktop/issues/4992)
- [Telegram Bugs — Message width varies on caption length](https://bugs.telegram.org/c/27759)
- [Telegram Bugs — Fixed min width for narrow photos with caption](https://bugs.telegram.org/c/6015/7)
- [pyTelegramBotAPI #861 — Is there a way to control image width/height?](https://github.com/eternnoir/pyTelegramBotAPI/issues/861)

Conclusión de todas: el ancho de una foto+pie lo decide el cliente de Telegram, no el
remitente. Ni la resolución, ni el aspect ratio, ni mandarla como `document` en vez de
`photo` lo arregla (como `document` la preview sale más pequeña, no más ancha).

## Código de referencia (ya retirado de `app/api/main.py`)

```python
_TEST_ID = "_test_future_shapers"
_TEST_OPP = {
    "identifier": _TEST_ID,
    "title": "Future Shapers",
    "type": "YOUTH_EXCHANGE",
    "country_code": "IT",
    "summary": "...",
}

async def _get_card_opp(identifier: str) -> dict[str, Any]:
    if identifier == _TEST_ID:
        return _TEST_OPP
    row = await repo.get_by_identifier(identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return row

@app.get("/o/{identifier}", include_in_schema=False)
async def opportunity_preview_page(identifier: str) -> Response:
    opp = await _get_card_opp(identifier)
    base = (cfg.map_public_url or "https://mapa.proactivefuture.eu").rstrip("/")
    image_url = f"{base}/o/{identifier}/image.png"
    dest = base if identifier == _TEST_ID else f"{base}/mapa?o={identifier}"
    page = f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<title> </title>
<meta property="og:site_name" content="Corradi Erasmus+">
<meta property="og:image" content="{image_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="300">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<script>location.replace({dest!r});</script>
</head><body>Redirigiendo a <a href="{dest}">{dest}</a>&hellip;</body></html>"""
    return Response(content=page, media_type="text/html", headers={"Cache-Control": "no-cache"})

@app.get("/o/{identifier}/image.png", include_in_schema=False)
async def opportunity_preview_image(identifier: str) -> Response:
    opp = await _get_card_opp(identifier)
    png = opportunity_card.render(opp)
    return Response(content=png, media_type="image/png",
                     headers={"Cache-Control": "public, max-age=300"})
```

Y el envío, en vez de `publish_photo_to_channel`:

```python
from telegram import LinkPreviewOptions

full = pub.format_opportunity(opp, buttons=True)
lines = full.split("\n")
lines[0] = f'{flag} <b><a href="{base}/o/{opp["identifier"]}">{opp["title"]}</a></b>'
text = "\n".join(lines)
await bot.send_message(
    chat_id=cfg.telegram_channel_id, text=text,
    parse_mode=ParseMode.HTML, reply_markup=pub.opportunity_keyboard(opp),
    link_preview_options=LinkPreviewOptions(
        url=f"{base}/o/{opp['identifier']}", show_above_text=True, prefer_large_media=True,
    ),
)
```

Para retomarlo: volver a montar las dos rutas en `app/api/main.py`, añadir `/o/*` a
`@publico` en `docker/Caddyfile`, y cambiar `pipeline.commit()` para usar `send_message` +
`LinkPreviewOptions` en vez de `publish_photo_to_channel()`.
