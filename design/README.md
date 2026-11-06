# Corradi · identidad visual

Logo oficial desde el 6 de noviembre de 2026: **«Estrella polar»**. Es una C abierta que guarda dentro una estrella de cuatro puntas, como la de una rosa de los vientos. Representa orientación: ayudamos a encontrar el rumbo en Europa.

Todo se genera desde [`build.py`](build.py), así que la geometría y los colores están en un solo sitio. Para regenerar las piezas:

```bash
.venv/bin/python design/build.py
```

Hace falta Google Chrome instalado: se usa sin interfaz para exportar los PNG.

## Colores

| Nombre | Hex | Uso |
|---|---|---|
| Arcilla | `#ad573e` | Color principal de marca: disco del logo, botones, acentos |
| Arcilla oscura | `#89422d` | Hover y textos de enlace |
| Tinta | `#263528` | Texto y símbolo sobre fondo claro |
| Tinta profunda | `#1b281e` | Fondos oscuros (pie, banners) |
| Papel | `#f7f0e2` | Fondo general |
| Blanco cálido | `#fffaf1` | Tarjetas y el símbolo sobre arcilla |
| Salvia | `#dce1ca` | Fondos suaves y decoración |

## Tipografía

- **Georgia**, en regular y cursiva: el nombre «Corradi» y los titulares.
- **Manrope**, en 600 y 700: textos, botones y la línea «ERASMUS+ EN CLARO», que va en mayúsculas y con mucho espaciado.

Los SVG con texto usan estas fuentes del sistema. Si se abren en un equipo sin Georgia, el nombre se verá en otra serif. Para imprimir o enviar a terceros, usa los PNG.

## Reglas de uso

- Deja aire alrededor del símbolo: como mínimo, la mitad del grosor de la C.
- Sobre arcilla, el símbolo va siempre en blanco cálido. Sobre fondo claro, en tinta o en arcilla.
- No lo gires, no lo deformes, no le pongas sombras ni cambies sus colores.
- El símbolo solo funciona desde 16 px. Por debajo de 32 px usa el favicon, que ya va con el disco arcilla.

## Qué subir a cada red (lo haces tú)

| Dónde | Archivo | Nota |
|---|---|---|
| Instagram, foto de perfil | `png/instagram-profile-1080.png` | Instagram la recorta en círculo; el símbolo queda dentro de la zona segura |
| Canal de Telegram, foto | `png/telegram-channel-640.png` | |
| Canal de WhatsApp, foto | `png/whatsapp-channel-640.png` | |
| Bot de Telegram, foto (BotFather → `/setuserpic`) | `png/telegram-bot-640.png` | Versión distinta: fondo tinta y burbuja de chat, para que se reconozca que es el bot |
| Bot de Telegram, imagen de descripción (BotFather → `/setdescriptionpic`, si tu versión de BotFather lo ofrece) | `png/telegram-bot-description-640x360.png` | Se ve antes de pulsar «Iniciar» |
| Firma de email, presentaciones, documentos | `png/corradi-logo-horizontal@2x.png` (fondo claro) o `png/corradi-logo-horizontal-white@2x.png` (fondo oscuro) | Fondo transparente |
| Cartelería, redes en formato vertical | `png/corradi-logo-stacked.png` | |
| Imprenta o diseño (vectorial) | `svg/*.svg` | |

## Qué ya está actualizado en la web

| Pieza | Archivo publicado | Origen |
|---|---|---|
| Símbolo del menú y del pie | `app/api/static/logo-mark.svg` | `svg/corradi-mark-ink.svg` |
| Logo completo | `app/api/static/logo.svg` | `svg/corradi-logo-horizontal.svg` |
| Favicon | `favicon.svg` y `favicon.ico` (16/32/48) | `svg/favicon.svg`, `png/favicon.ico` |
| Icono de iOS | `apple-touch-icon.png` (180 px) | `png/apple-touch-icon-180.png` |
| Iconos de la app instalable | `icon-192.png`, `icon-512.png`, `icon-maskable-512.png` | `png/icon-*.png` |
| Imagen al compartir un enlace | `og.png` (1200×630) | `png/og-share-1200x630.png` |
| Marca del mapa y de /publicar | SVG inline | Misma geometría |

## Archivos

- `svg/`
  - **Símbolo:** `corradi-mark-ink`, `-clay`, `-white`.
  - **Iconos:** `corradi-icon-circle`, `corradi-icon-square`.
  - **Logo horizontal y vertical:** `corradi-logo-horizontal(-white)`, `corradi-logo-stacked(-white)`.
  - **Redes:** las mismas piezas que en `png/`.
- `png/`
  - **Las mismas piezas, exportadas.**
  - **Versiones grandes con fondo transparente:** `corradi-mark-*@5x.png` y `corradi-logo-horizontal*@2x.png`.
  - **Favicon:** `favicon-16/32/48.png` y `favicon.ico`.
