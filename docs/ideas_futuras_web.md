# Ideas futuras para el mapa (mapa.proactivefuture.eu)

Recopilación de ideas de mejora de la web, sin implementar todavía. Fecha del análisis: 2026-07-25.
Contexto en el momento del análisis: 41 oportunidades en BD, 26 abiertas.

## Estado real de los datos (verificado en BD de producción, 41 filas)

| Campo | Relleno | % | Notas |
|---|---|---|---|
| `topic` | 40/41 | 97.6% | Texto libre en español, no normalizado a taxonomía |
| `contact_information` | 31/41 | 75.6% | Email/teléfono, no nombre de asociación |
| `participant_min_age` | 29/41 | 70.7% | Sí se extrae |
| `max_participants` | 24/41 | 58.5% | Sí se extrae |
| `participant_max_age` | 21/41 | 51.2% | Sí se extrae |
| `cost` | 19/41 | 46.3% | Sí se extrae |
| **organiser / asociación** | **0/41** | **0%** | **No existe el campo. No se extrae en ningún sitio del pipeline (prompt, dominio, BD, API)** |

El nombre de la organización tampoco aparece de forma fiable en `title` ni `summary` (revisados varios ejemplos): los títulos son nombres de proyecto ("Waves of Cooperation", "Windmill Tree in Nemoland"), no el nombre de quien lo organiza. Para tener la pestaña de asociaciones hay que **añadir extracción nueva** (columna `organiser_name` + prompt), no es un dato ya capturado y sin usar.

---

## Tier 0 — Rápidas, solo tocar `mapa.html`, datos ya en la API

1. ~~**Filtro por edad**~~ — **HECHO (2026-07-27)**. Campo "Tengo N años" dentro del panel
   agrupado de filtros. De paso, ese panel unificó Categoría/Fechas/Países (antes tres
   desplegables sueltos) y separó Urgencia como grupo propio, de modo que añadir filtros
   nuevos ya no implica meter otro botón en la barra.
2. **Badge de coste**: `cost = 0` → "Gratis · financiado por Erasmus+". Dato ya en la API, sin usar en la tarjeta.
3. **Plazas** (`max_participants`) en la tarjeta: "20 plazas".
4. **Botón "Añadir al calendario"** por oportunidad (evento con la deadline, ver detalle abajo).
5. **Favoritas en `localStorage`** + chip "Mis guardadas" (ver detalle abajo).
6. **Glosario** TC/YE/ESC en el modal de info que ya existe.
7. **Ordenar lista**: por cierre / inicio / más nueva.
8. **Selector ES/EN** de la interfaz (los títulos ya vienen en su idioma original, solo traduce los textos fijos).

## Tier 1 — Pestañas nuevas

9. **Explorar por temática**: normalizar `topic` a una taxonomía cerrada (~10 temas) añadida por el LLM además del texto libre actual. Vista de mosaico "🌱 Medio ambiente · 6 abiertas".
10. **Pestaña Asociaciones**: requiere añadir `organiser_name` (+ opcional `organiser_country`, `organiser_url`) al prompt de extracción y a la BD. Ficha por asociación con nº de proyectos publicados y abiertos actuales.
11. **Archivo / cerradas**: hoy una oportunidad cerrada desaparece sin dejar rastro. Un archivo da volumen histórico y alimenta el punto 12.
12. **Predicción de recurrencia**: con archivo + organizador, detectar patrones de "esta asociación suele abrir en marzo".

## Tier 2 — Inteligencia

13. **Chatbot RAG**: ya existe `vector(768)` + índice HNSW en `projects.embedding` (`db/migrations/0001_init.sql`) y `app/llm/embeddings.py`. Endpoint que hace embed de la pregunta, busca top-5 por coseno entre abiertas, responde citando `identifier`s reales. Necesita rate-limit por IP desde el día uno.
14. **Matcher sin LLM**: 4 preguntas (edad, país de origen, temas, fechas) que puntúan el JSON ya cargado en el navegador. Cero coste, cubre gran parte de lo que resolvería el chatbot.
15. **Búsqueda semántica** en el buscador actual, reutilizando los mismos embeddings.
16. **Alertas por tema+país vía el bot de Telegram**: deep link `t.me/corradi_erasmus_bot?start=alert_ENV_IT`.
17. **Calculadora de beca de viaje**: bandas de distancia de Erasmus+ son públicas y formulaicas; ya hay lat/lon de origen y destino.

## Tier 3 — Difusión (clave por la restricción de WhatsApp Channel sin API)

18. **Página propia por oportunidad con `og:` específicos** (hoy `/2026-0040` solo redirige al mapa genérico, ver `app/api/main.py:196`). Cada link compartido a mano se vendería solo.
19. **Widget embebible** (`<iframe>`) para que los socios lo pongan en su web.
20. **RSS + JSON documentado** como dato abierto (línea de dissemination del KA210).
21. **Tarjeta vertical para Stories** (1080×1920) por oportunidad.
22. **QR imprimible** del mapa para carteles físicos.

## Tier 4 — Panel para el coordinador

23. **Dashboard de impacto**: oportunidades por país/tema/mes, visitas, envíos de la comunidad — alimenta el informe final del KA210.
24. **Contador de vistas/clics por oportunidad** → qué temáticas mueven de verdad, habilita "🔥 más vistas esta semana".
25. **Distintivo de procedencia**: verificada por el coordinador / comunidad / SALTO-YOUTH.

## Otras (más especulativas)

26. Vista de línea de tiempo (barras por mes).
27. Comparar dos oportunidades en paralelo.
28. Mapa de calor por país en vez de solo pines.
29. Captura de "ninguna me encaja" (tema+país deseado) como dato de demanda no cubierta.
30. Sugerencia de "siguiente paso" (YE → TC → ESC) como narrativa de progresión.

---

## Orden recomendado (repetido de la conversación original)

1. Tier 0 completo (un día de trabajo, mismo fichero).
2. Página por oportunidad con OG propio (#18).
3. Añadir `organiser_name` + `topics[]` normalizados al extractor — desbloquea #9 y #10.
4. Pestañas Temática y Asociaciones.
5. Matcher de 4 preguntas (#14) + calculadora de beca (#17).
6. Chatbot RAG (#13), al final, apoyándose en temáticas ya normalizadas.

## Notas de implementación para dudas ya resueltas

- **Filtro de edad**: el campo existe y se extrae (`participant_min_age`/`participant_max_age`), ~70%/51% de relleno. Viable ya, sin cambios de esquema. Ya implementado; con ese relleno parcial, el criterio es **permisivo**: solo se oculta una oportunidad si el dato existe Y no encaja, nunca por faltar el dato (mismo criterio que el resto del mapa).
- **Añadir al calendario**: no requiere backend. Un botón que genera un `.ics` al vuelo en el propio JS (`data:text/calendar` con `VEVENT` usando `application_deadline` como fecha, o mejor `start_date`/`end_date` para el evento en sí) y lo descarga, o un link `https://calendar.google.com/calendar/render?action=TEMPLATE&...` para Google Calendar directamente. Cada usuario decide si lo guarda en su propio calendario; no se guarda nada en el servidor.
- **Favoritas**: sí, 100% en el dispositivo del usuario vía `localStorage` (array de `identifier`s). Sin cuentas, sin backend, sin RGPD. Limitación: no sincroniza entre dispositivos del mismo usuario ni sobrevive a borrar datos del navegador — para este caso de uso (visita puntual a un mapa) es suficiente.
- **Asociación/organizador**: no se captura hoy, 0% de las 41 oportunidades tienen ese dato en ningún campo (ni siquiera embebido en título/resumen de forma fiable). Para la pestaña de asociaciones hay que añadir un campo nuevo al prompt de extracción y a la tabla `projects`, y solo se rellenará hacia adelante (las 41 existentes se quedarían sin ese dato salvo revisión manual).
