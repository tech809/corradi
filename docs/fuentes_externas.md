# Fuentes externas para ingesta automática (análisis 2026-07-22)

Investigación sobre de qué fuentes podría CORRADI-BOT ingerir oportunidades **automáticamente**
(además del envío manual por Telegram). Resumen honesto: **ninguna fuente oficial (SALTO,
European Youth Portal, ESC) publica una API REST pública documentada** de oportunidades; la
automatización real es casi siempre **scraping HTML**. No hay endpoints inventados.

| # | Fuente | Qué es / relevancia ES | Acceso automatizable | Coste/límites | Datos | Esfuerzo/fiabilidad |
|---|--------|------------------------|----------------------|---------------|-------|---------------------|
| 1 | **SALTO European Training Calendar** (`salto-youth.net/tools/european-training-calendar/browse/`) | Cursos TCA / trainings / seminarios. Alto volumen. | Sin API ni RSS (solo email vía MySALTO). Scraping de fichas. | Gratis; revisar ToS. | **Estructurados**: título, fechas, país, deadline, tema, enlace. | Medio / alta |
| 2 | **Agregadores de infopacks** (tavoeuropa.eu/youth-exchanges, erasmuser.com, youthcluster.org, erasmusgeneration.org) | Youth Exchanges + TC con deadlines, ya curados. Muy relevante. | Scraping; algunos con RSS de WordPress (`/feed/`). | Gratis. | Semi-estructurado → pasa por el LLM igual. | Bajo-medio / media |
| 3 | **Eurodesk – Programmes finder** (`programmes.eurodesk.eu`) | Red oficial que alimenta el European Youth Portal. | Sin API pública; scraping. | Gratis. | Estructurado por categorías. | Medio / media |
| 4 | **European Youth Portal / ESC — voluntariado** (`youth.europa.eu/go-abroad/volunteering/opportunities_en`) | Mayor volumen de voluntariado ESC filtrable por España. | Sin API pública documentada; buscador dinámico (endpoint JSON interno **no verificado**), detalle tras login. | Gratis; parte gated. | Buena (país, duración, deadline, org). | Alto / media |
| 5 | SALTO Otlas · ESC PASS · Erasmus+ Project Results / EU Open Data | Partner-finding / reclutamiento / proyectos ya cerrados. | — | — | **No son oportunidades abiertas publicables.** | Descartar |
| 6 | Cuentas públicas (IG @youthexchanges, canales Telegram) | Alto volumen real. | Scraping de redes: frágil y contra ToS. | — | Texto libre. | No prioritario |

## Recomendación (mejor valor/esfuerzo)

1. **SALTO European Training Calendar** — datos ya estructurados (fechas, país, deadline,
   enlace), fuente oficial, HTML estable. Casi no necesita el LLM. Empezar por aquí.
2. **2 agregadores de infopacks** (tavoeuropa.eu + erasmuser.com) — cubren Youth Exchanges/TC
   que SALTO no lista; texto que ya sabemos pasar por el pipeline Gemini. Esfuerzo bajo, hay
   que mantener los selectores.
3. **Portal ESC (voluntariado)** — mayor volumen para España, pero **segunda fase**: sin API
   pública, hay que inspeccionar el endpoint XHR interno o scrapear con sesión. Esfuerzo alto.

**Descartar** Otlas, PASS y las plataformas de resultados/open data (no son plazas abiertas).

> Nota operativa: antes de scrapear SALTO o youth.europa.eu, revisar Términos y `robots.txt`,
> con ritmo de peticiones bajo y User-Agent identificable. La ingesta automática debe pasar por
> el MISMO `pipeline.ingest()` (clasifica + deduplica) para no publicar basura ni duplicados.
