# Ideas futuras para el mapa (mapa.proactivefuture.eu)

Recopilación de ideas de mejora de la web. Última revisión: 2026-07-28 (tras implementar SEO,
temática y la página de estadísticas). Contexto en esta revisión: 80 oportunidades en BD.

## Estado real de los datos (verificado en BD de producción, 80 filas)

| Campo | Relleno | % | Notas |
|---|---|---|---|
| `topic` | ~78/80 | ~97% | Texto libre en español/inglés; desde 2026-07-28 también se agrupa en cliente en ~10 temas por keyword-matching, ver #9 |
| `contact_information` | ~60/80 | ~75% | Email/teléfono, no nombre de asociación |
| `participant_min_age` | ~56/80 | ~70% | Sí se extrae |
| `organiser_name` | 19/80 | **~24%** | Sí se extrae (`EXTRACTABLE_FIELDS` en `app/domain/project.py`, columna en `projects`) — **corrige la cifra de 0% de la revisión anterior, que estaba desactualizada** |
| `max_participants` | ~47/80 | ~58% | Sí se extrae |
| `participant_max_age` | ~41/80 | ~51% | Sí se extrae |
| `cost` | ~37/80 | ~46% | Sí se extrae |

`organiser_name` ya se extrae del mensaje original cuando aparece explícito, pero muchas fuentes
(sobre todo SALTO-YOUTH) no lo mencionan de forma clara — de ahí el ~24% en vez de un rellenado
completo. No hace falta ninguna extracción nueva para la pestaña de asociaciones: ya existe.

---

## Hecho

1. ~~**Filtro por edad**~~ — 2026-07-27. Panel agrupado de filtros (Categoría/Edad/Fechas/País).
2. ~~**Ordenar lista**~~ — 2026-07-28. "Últimas subidas" (por defecto) / "Cierran antes", encima del panel de oportunidades.
3. ~~**Explorar por temática** (#9 de la revisión anterior)~~ — 2026-07-28. Taxonomía cerrada de
   ~10 temas (medio ambiente, arte y cultura, tecnología, inclusión, deporte y salud, idiomas,
   ciudadanía, empleabilidad, educación no formal + "otras") por **keyword-matching en cliente**
   sobre `topic`/`title`/`summary` — sin tocar el LLM ni la BD. Nueva pestaña "Temas" dentro del
   diálogo de Filtros existente (no una vista de mosaico aparte, para no complicar la navegación).
4. ~~**Pestaña Asociaciones** (#10)~~ — 2026-07-28. Sección "Asociaciones" dentro de la nueva
   página `/estadisticas`: lista de `organiser_name` con nº de proyectos totales y abiertos.
5. ~~**Archivo / cerradas** (#11)~~ — 2026-07-28. Sección "Archivo de cerradas" en
   `/estadisticas`, últimas 60 oportunidades con `status IN ('closed','expired')`.
6. ~~**Vista de línea de tiempo** (#26) + **top países**~~ — 2026-07-28. Sección de barras
   mensuales (últimos 12 meses) y ranking de países en `/estadisticas`.
7. ~~**SEO** (#18, página propia por oportunidad con `og:` específicos)~~ — 2026-07-28.
   `/{short_id}` (antes un 302 directo al mapa) ahora sirve una mini-página con `<title>`,
   meta-description y OG reales de esa oportunidad, con redirección automática a los 4s hacia
   `/mapa?o=...` para quien hace clic. Además: `/robots.txt`, `/sitemap.xml` dinámico (un `<url>`
   por oportunidad abierta) y JSON-LD `WebSite` en `mapa.html`.

## Descartado / rebajado de alcance (con motivo)

- **Mapa de calor por país (#28)** — descartado como mapa geográfico de verdad (necesitaría
  GeoJSON/librería nueva). Sustituido por el ranking simple "Países con más oportunidades" en
  `/estadisticas`, que da la misma información sin añadir peso ni complejidad a la página.
- **Contador de vistas/clics por oportunidad (#24) y "visitas por día"** — no implementado. Hoy
  no existe NINGUNA instrumentación de clic en "Más info"/"Form"/"Infopack", y el contador de
  visitas (`counters` table, `db/migrations/0004_counters.sql`) es acumulativo sin granularidad
  diaria. Añadirlo bien requiere: tabla nueva, endpoint nuevo y beacons JS en cada botón — se deja
  fuera de esta pasada a propósito para no complicar la web; queda como Tier 4 si hace falta de
  verdad para el informe del KA210.
- **Vista de mosaico para temática** — descartada a favor de una pestaña más dentro del diálogo
  de Filtros ya existente (ver #9 arriba): mismo resultado (filtrar por tema), una superficie
  nueva menos que mantener.

## Pendiente

### Tier 2 — Inteligencia

- **Chatbot RAG** vía embeddings (`projects.embedding`, ya existe el índice).
- **Matcher sin LLM**: 4 preguntas (edad, país, temas, fechas) que puntúan el JSON ya cargado.
- **Búsqueda semántica** reutilizando los embeddings existentes.
- **Alertas por tema+país vía Telegram** (deep link `t.me/corradi_erasmus_bot?start=alert_ENV_IT`).
- **Calculadora de beca de viaje** (bandas de distancia Erasmus+, ya hay lat/lon).

### Tier 3 — Difusión

- **Widget embebible** (`<iframe>`) para que los socios lo pongan en su web.
- **RSS + JSON documentado** como dato abierto (línea de dissemination del KA210).
- **Tarjeta vertical para Stories** (1080×1920) por oportunidad — ya existe algo similar para
  Instagram (`app/publisher/instagram_card.py`), reutilizable.
- **QR imprimible** del mapa para carteles físicos.

### Tier 4 — Panel para el coordinador

- **Dashboard de impacto** completo (país/tema/mes/envíos de la comunidad) para el informe final.
- **Contador de clics por oportunidad** (ver "Descartado" arriba — requiere instrumentación nueva).
- **Distintivo de procedencia**: verificada por el coordinador / comunidad / SALTO-YOUTH.

### Otras (más especulativas)

- Predicción de recurrencia ("esta asociación suele abrir en marzo") — se puede reconstruir ahora
  que existen `organiser_name` y el archivo de cerradas con histórico real.
- Comparar dos oportunidades en paralelo.
- Captura de "ninguna me encaja" (tema+país deseado) como dato de demanda no cubierta.
- Sugerencia de "siguiente paso" (YE → TC → ESC) como narrativa de progresión.
- Selector ES/EN de la interfaz.

## Notas de implementación para dudas ya resueltas

- **Filtro de edad**: criterio permisivo — solo se oculta una oportunidad si el dato existe Y no
  encaja, nunca por faltar el dato.
- **Añadir al calendario**: sin backend, `.ics`/link de Google Calendar generado en el propio JS.
- **Favoritas**: si se implementa, 100% en `localStorage`, sin cuentas ni RGPD.
- **Asociación/organizador**: SÍ se captura (~24% de cobertura, ver tabla arriba) — la pestaña de
  Asociaciones en `/estadisticas` usa el dato tal cual está hoy, sin extracción nueva.
