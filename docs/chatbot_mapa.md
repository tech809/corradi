# Chatbot del mapa — diseño y coste

Diseño (todavía **sin implementar**) de un asistente conversacional en
`mapa.proactivefuture.eu` para preguntar en lenguaje natural por las oportunidades
**abiertas**: _"¿hay algo en Italia en octubre para mayores de 25?"_, _"¿qué hay de medio
ambiente?"_, _"¿qué cierra esta semana?"_.

Fecha del análisis: **2026-07-27**. Recoge y sustituye a las ideas #13 (chatbot RAG) y #14
(matcher sin LLM) de [`ideas_futuras_web.md`](ideas_futuras_web.md).

---

## TL;DR

- **Arquitectura recomendada: meter el catálogo entero de oportunidades abiertas en el
  prompt en cada consulta.** Nada de RAG. Con 44 abiertas el catálogo completo son **6.713
  tokens medidos**, y el ahorro de hacer RAG de verdad son **~2 $/mes** a 100 consultas/día.
- **Coste**: ~**0,85 $ por cada 1.000 consultas** con `gemini-2.5-flash-lite`, el modelo que
  el proyecto ya usa. Es decir **~2,6 $/mes** a 100 consultas/día y **~26 $/mes** a
  1.000/día.
- El LLM **nunca escribe datos de oportunidades**: devuelve JSON con `identifier`s, y el
  navegador pinta las tarjetas con el JSON de `/api/map` que ya tiene descargado. Así es
  estructuralmente imposible que se invente una oportunidad.
- **UI**: un botón `✨ Preguntar` junto a `Filtros`, que abre un `<dialog>` con la misma
  "chrome" (`.info-dialog`) que ya usan Filtros e Información. Sin pestañas nuevas, sin
  burbuja flotante nueva (la de abajo ya está ocupada por Lista/Mapa en móvil).

---

## 1. Datos reales sobre los que trabaja el bot

Medido contra producción (`GET https://mapa.proactivefuture.eu/api/map`, 2026-07-27):
**44 oportunidades abiertas, 53,9 KB de JSON**. Relleno por campo sobre esas 44:

| Campo | Relleno | % | ¿Sirve para responder? |
|---|---|---|---|
| `identifier`, `title`, `type`, `topic`, `summary` | 44/44 | 100% | Sí — el núcleo de la respuesta |
| `application_deadline` (+ `deadline_estimated`) | 44/44 | 100% | Sí — "¿qué cierra pronto?" |
| `country_code`, `location`, `start_date`, `end_date` | 43/44 | 98% | Sí — "en Italia", "en octubre" |
| `application_url` | 41/44 | 93% | Sí (lo pinta el front, no el LLM) |
| `contact_information` | 39/44 | 89% | No se manda al prompt (dato de contacto de terceros) |
| `infopack_url` | 36/44 | 82% | Sí (lo pinta el front) |
| `max_participants` | 36/44 | 82% | Marginal |
| `cost` | 26/44 | 59% | Sí — "¿hay algo gratis?" |
| `participant_min_age` | 25/44 | 57% | Sí, **con cuidado** |
| `participant_max_age` | **14/44** | **32%** | Sí, **con mucho cuidado** |

**El dato crítico es el último.** La pregunta del enunciado ("para mayores de 25") solo se
puede contestar bien en 1 de cada 3 fichas. El bot **no debe descartar** una oportunidad por
un rango de edad que no consta: tiene que decir "en estas 3 no consta la edad, confírmalo en
el infopack" — exactamente el mismo criterio que ya sigue el filtro de edad del mapa
(`matchesDate()` / rango de edad: dato ausente = **nunca oculta**).

Dos notas más:

- `topic` es **texto libre en español**, no una taxonomía cerrada. Para un LLM esto es una
  ventaja, no un problema: es justo lo que sabe interpretar. Para el matcher sin LLM (opción
  C) sí sería un problema.
- `organiser_name` **existe ya en BD** (migración `0006_organiser.sql`, y está en el prompt
  de extracción), pero **no está en la lista blanca `_PUBLIC_FIELDS`** de `app/api/main.py`,
  así que hoy no sale por `/api/map`. Si se quiere que el bot responda "¿quién lo organiza?",
  hay que añadirlo ahí (decisión consciente, ver §8).

---

## 2. Las tres arquitecturas

### (a) Catálogo completo en el prompt — **recomendada**

```
pregunta → [instrucciones + catálogo de las 44 abiertas + pregunta] → Gemini
         → JSON {respuesta, ids:[...]} → el front pinta tarjetas desde /api/map
```

No hay recuperación, no hay embeddings, no hay ranking. Se le da al modelo **todo el
catálogo** y él decide. El catálogo se genera desde `repo.list_open()` como texto compacto
(una línea por oportunidad) y se cachea en memoria unos minutos.

Formato de línea propuesto (~153 tokens/oportunidad medidos, incluyendo `summary`):

```
2026-0043 | Waves of Cooperation | TC | Vilnius, Lithuania, LT | 2026-10-11/2026-10-18 |
cierra 2026-07-27 | edad 18+ | gratis | partnership building, non-formal education, … |
El proyecto "Waves of Cooperation" es un curso de formación internacional de 6 días…
```

**Ventajas**
- Cero infraestructura nueva. Un endpoint, una llamada a Gemini con el mismo patrón que
  `app/llm/extractor.py` ya usa (`generate_content` + `response_mime_type="application/json"`
  + `with_retry`). Nada de pgvector en la ruta de lectura.
- **Responde preguntas agregadas**, que es donde el RAG se rompe: "¿cuántas hay en Italia?",
  "¿qué cierra esta semana?", "enséñame todas las de octubre", "¿hay algo gratis?". El top-5
  por coseno no puede contestar ninguna de esas.
- Filtros duros (fecha, edad, país) los aplica el modelo viendo **todos** los candidatos, no
  los 5 que el coseno haya considerado "parecidos" a una frase que mezcla tema y filtros.
- Se depura leyendo un prompt. No hay que preguntarse "¿por qué no recuperó esta?".

**Desventaja**: el coste crece linealmente con el nº de oportunidades abiertas. Ver §3.

### (b) RAG de verdad con los embeddings existentes

La infraestructura está: `vector(768)` + índice HNSW (`db/migrations/0001_init.sql`),
`app/llm/embeddings.py::embed()`, y `repo.find_similar()` ya hace exactamente esta consulta
(`ORDER BY embedding <=> %s`) para deduplicar. Serían ~30 líneas.

**El problema no es el coste, es la calidad.** Los embeddings guardados se calcularon sobre
el texto de la oportunidad para **deduplicar**, no para responder preguntas. Una pregunta
como "algo en Italia en octubre para mayores de 25" es mayoritariamente **filtros
estructurados**, y el coseno sobre 768 dimensiones no distingue "octubre" de "noviembre" ni
"Italia" de "Irlanda" de forma fiable. Con top-5 sobre un universo de 44, se estaría tirando
el 89% del catálogo para ahorrar **medio céntimo por cada 10 consultas**.

Sería la arquitectura correcta con **cientos o miles** de oportunidades abiertas. Con 44, no.

### (c) Matcher sin LLM (idea #14) — coste cero, **complemento, no sustituto**

4 preguntas (edad, país, temas, fechas) puntuando el JSON que el navegador **ya tiene
descargado**. Cero coste, cero latencia, cero riesgo, funciona sin conexión a Gemini.

Cubre bien "quiero algo en octubre en Italia y tengo 25 años" — pero eso el mapa ya lo hace
con los filtros actuales (tipo + urgencia + edad + fechas + país, todos combinables). Lo que
**no** cubre es el lenguaje libre y el matiz temático ("algo para trabajar con refugiados",
"algo donde aprenda a escribir proyectos"), que es justo donde `topic` + `summary` en texto
libre brillan y donde un LLM aporta de verdad.

**Rol recomendado**: no construirlo como producto aparte, sino usar su lógica como
**fallback** cuando Gemini falle o cuando salte el rate-limit (§6).

---

## 3. Coste en tokens — números medidos

### Precios (Gemini API, tier de pago, consultados 2026-07-27)

| Modelo | Entrada | Salida | Entrada cacheada |
|---|---|---|---|
| `gemini-2.5-flash-lite` (**el que ya usa el proyecto**, `cfg.llm_model`) | 0,10 $/1M | 0,40 $/1M | ~0,025 $/1M (−75%) |
| `gemini-2.5-flash` | 0,30 $/1M | 2,50 $/1M | — |
| `gemini-embedding-001` (`cfg.embed_model`) | 0,15 $/1M | — | — |

### Tokens medidos de verdad

Contados con el endpoint `countTokens` de la API real (que **no consume cuota de
generación**) sobre las 44 oportunidades abiertas de producción:

| Contenido | Caracteres | **Tokens** | Tokens/oportunidad |
|---|---|---|---|
| JSON crudo de `/api/map` tal cual | 53.567 | **17.724** | 403 |
| Catálogo compacto **con** `summary` | 23.706 | **6.713** | **153** |
| Catálogo compacto **sin** `summary` | 9.739 | **3.866** | 88 |

Conclusión inmediata: **no mandar el JSON crudo**. Compactarlo a texto plano ahorra el 62%
de los tokens de entrada sin perder nada útil (se caen `latitude`, `longitude`,
`telegram_message_id`, `channel_url`, `status`, `approx_location`… que el LLM no necesita
porque el front ya los tiene).

### Coste por consulta

Presupuesto de tokens para (a), suponiendo un bloque de instrucciones de ~600 tokens
(estimado, no medido — el prompt aún no está escrito) y una respuesta de ~250 tokens:

| | (a) catálogo completo | (a) sin `summary` | (b) RAG top-5 |
|---|---|---|---|
| Instrucciones | 600 | 600 | 600 |
| Catálogo | 6.713 | 3.866 | 765 (5 × 153) |
| Pregunta + historial | ~200 | ~200 | ~200 |
| **Entrada total** | **~7.500** | **~4.700** | **~1.600** |
| Salida | ~250 | ~250 | ~250 |
| Embedding de la pregunta | — | — | 25 tok |
| **Coste/consulta** | **0,00085 $** | 0,00057 $ | **0,00026 $** |
| **Coste/1.000 consultas** | **0,85 $** | 0,57 $ | **0,26 $** |

### Escenarios

| Volumen | (a) catálogo completo | (b) RAG top-5 | Diferencia |
|---|---|---|---|
| 100 consultas/día (3.000/mes) | **2,55 $/mes** (~2,2 €) | 0,78 $/mes | 1,77 $/mes |
| 1.000 consultas/día (30.000/mes) | **25,50 $/mes** (~22 €) | 7,80 $/mes | 17,70 $/mes |
| Pico de 5.000 en un día | 4,25 $ ese día | 1,30 $ ese día | 2,95 $ |

**A 100 consultas/día, hacer RAG ahorra 21 $ al año.** No compensa ni el día de desarrollo
extra, ni el riesgo de que el retrieval falle y el bot diga "no hay nada" cuando sí lo hay.

Como referencia de escala: el mapa lleva un contador de visitas propio; si cada visitante
hiciera **una** pregunta, 100 consultas/día equivalen a 100 visitas/día con conversión del
100%. Es un techo generoso para el tráfico realista de este proyecto.

### ¿Cuándo dejaría de valer (a)?

A 153 tokens por oportunidad:

| Abiertas | Tokens de catálogo | Coste/1.000 consultas |
|---|---|---|
| 44 (hoy) | 6,7k | 0,85 $ |
| 100 | 15k | 1,66 $ |
| 250 | 38k | 3,95 $ |
| 500 | 77k | 7,80 $ |

El límite técnico no es el contexto (flash-lite admite 1M tokens). El umbral práctico para
replantearse la arquitectura está en torno a **300–500 abiertas simultáneas**. Con el ritmo
actual eso queda muy lejos, y cuando llegue **la evolución natural no es RAG, es un
prefiltro determinista**: si la pregunta menciona un país o un mes, filtrar en SQL antes de
armar el catálogo. Es más barato, más predecible y más fácil de depurar que el coseno.

### Caché implícita: no contar con ella

Gemini 2.5 aplica **caché implícita** con ~75% de descuento sobre el prefijo repetido a
partir de ~1.024 tokens. En teoría, instrucciones + catálogo (~7.300 tokens fijos) darían
hit y el coste bajaría a ~0,30 $/1.000. En la práctica **no hay que presupuestarlo**: el
prefijo se invalida cada vez que entra o cierra una oportunidad (a diario), el TTL es corto
y no está documentado que flash-lite lo aplique igual. Trátese como una rebaja agradable si
llega, no como parte del cálculo.

### Avisos honestos sobre estas cifras

- Los **6.713 tokens del catálogo son una medida real**; los 600 de instrucciones y los 250
  de salida son **estimaciones**. Si el prompt de sistema acaba en 1.500 tokens, el coste
  sube un ~12%. Nada que cambie la decisión.
- **La latencia no está medida.** Con ~7.500 tokens de entrada, flash-lite debería responder
  en el orden de 1–3 s, pero eso hay que comprobarlo en la fase 0 (§7).
- **No sé en qué tier está la API key del proyecto.** Si estuviera en tier gratuito (30 RPM),
  el chat público competiría por la misma cuota que el pipeline de extracción, que es la
  función crítica. Ver §8.

---

## 4. Diseño de la UI

### Dónde vive

**Un botón `✨ Preguntar` en la barra `.filters`, a la izquierda de `Filtros`**, que abre
`<dialog id="chatDialog" class="info-dialog">`.

Por qué esa y no las otras opciones:

| Opción | Veredicto |
|---|---|
| **Botón en la barra de filtros + `<dialog>`** | ✅ Buscar / Filtros / Preguntar son las **tres formas de encontrar algo**, y quedan juntas donde el usuario ya mira. Reutiliza `.info-dialog` tal cual (cabecera fija + `.info-body` con scroll + pie fijo), que ya sirve para Filtros y para Información. Cero CSS estructural nuevo. |
| Burbuja flotante abajo a la derecha | ❌ Colisiona con `.view-bubble` (☰ Lista/Mapa), que en móvil ya ocupa esa zona. Dos burbujas flotantes en una pantalla de 375px es una pelea. |
| Tercer estado de la vista móvil (Lista / Mapa / **Chat**) | ❌ Rompe el patrón binario de `.view-bubble` ("enseña SIEMPRE la vista a la que vas"), que con tres estados deja de ser evidente. Y en escritorio no hay nada que alternar. |
| Pestaña de navegación arriba | ❌ Hoy no existe barra de pestañas. Introducir un nivel de navegación entero para una función es desproporcionado. |

### Cómo se ve

Reutilizando el sistema visual existente sin inventar nada:

```
┌─ Preguntar sobre las oportunidades ──────────────  ✕ ─┐   .info-head
│                                                        │
│  Pregunta con tus palabras qué buscas. Solo             │   .fp-hint
│  respondo sobre las 44 abiertas ahora mismo.            │
│                                                        │
│  [⏳ ¿Qué cierra esta semana?]  [🌱 Medio ambiente]     │   .chip (sugerencias)
│  [🇮🇹 Algo en Italia]  [🎓 Tengo 19 años]               │
│                                                        │
│  ─────────────────────────────────────────────────     │   .info-body (scroll)
│  Tú: ¿hay algo en Italia en octubre para +25?          │
│                                                        │
│  He encontrado 2 que encajan. En una tercera no         │
│  consta la edad máxima, la incluyo por si acaso:        │
│                                                        │
│  ┌──────────────────────────────────────────┐          │   ← .card, EL MISMO
│  │ [Training Course]        [📅] [🔗]       │          │     componente de la lista
│  │ Waves of Cooperation                     │          │
│  │ 🇮🇹 Roma, Italia · 📅 11-18 oct · 🏷️ …   │          │
│  │ ⏳ Cierra en 5 días                      │          │
│  │ [ℹ️ Más info] [📄 Infopack] [✍️ Form]    │          │
│  └──────────────────────────────────────────┘          │
│                                                        │
│  [ 🗺️ Ver estas 3 en el mapa ]                         │   .btn
├────────────────────────────────────────────────────────┤
│  [ Escribe tu pregunta…                    ]  [ → ]    │   .fp-foot (pie fijo)
└────────────────────────────────────────────────────────┘
```

Decisiones concretas:

1. **Las tarjetas de resultado son literalmente las mismas `.card` de la lista**, generadas
   por la misma función de render a partir del array `all` que el navegador ya tiene. El chat
   no es una isla con su propio estilo: es otra puerta de entrada a las mismas fichas, con
   los mismos botones (Más info / Infopack / Form / 📅 Recordar / 🔗 Compartir).
2. **`🗺️ Ver estas N en el mapa`** aplica un filtro nuevo `state.only = Set(identifiers)` y
   cierra el diálogo. Así el chat se integra como **un filtro más** del mapa en vez de ser una
   pantalla paralela — y el usuario acaba donde ya sabe moverse.
3. **Chips de sugerencia** al abrir, resolviendo el arranque en frío (un cuadro de texto vacío
   no le dice a nadie qué se puede preguntar). Reutilizan `.chip` tal cual.
4. **Contador visible** ("Solo respondo sobre las 44 abiertas ahora mismo") fijando la
   expectativa: esto no es ChatGPT, es un buscador del catálogo.
5. **Estado de carga**: el `.skeleton` con `@keyframes shimmer` que ya existe, no un spinner
   nuevo.
6. **Errores y avisos** por el `toast` que ya existe.
7. En móvil el `<dialog>` ya sale a ancho casi completo con `.info-body { max-height: 70vh }`
   — mismo comportamiento que Filtros hoy, no hace falta variante aparte.
8. Añadir un apartado al modal de Información ("Cómo funciona este mapa") explicando qué es
   el asistente y advirtiendo de que **no hay que escribir datos personales** en él.

---

## 5. Endpoint y contrato

`POST /api/chat` — hay que **añadirlo a la lista blanca `@publico` de `docker/Caddyfile`**
(línea 15), o Caddy devolverá 404 aunque la ruta exista en FastAPI.

**Petición**
```json
{ "pregunta": "¿hay algo en Italia en octubre para mayores de 25?" }
```

**Respuesta**
```json
{
  "respuesta": "He encontrado 2 que encajan. En una tercera no consta la edad máxima…",
  "ids": ["CORRADI-2026-0043", "CORRADI-2026-0031", "CORRADI-2026-0028"],
  "aviso": null
}
```

El campo clave es `ids`: **el LLM no devuelve títulos, ni fechas, ni URLs**. Devuelve
identificadores, y el front pinta las tarjetas desde su propia copia de `/api/map`. Se
apoya en el mismo `response_mime_type="application/json"` que ya usa `extractor.py`.

Esqueleto (mismo patrón que `app/llm/extractor.py`, no uno nuevo):

```python
# app/llm/chat.py
resp = with_retry(lambda: _gemini_client().models.generate_content(
    model=cfg.llm_model,                     # gemini-2.5-flash-lite, el de siempre
    contents=CHAT_PROMPT
        .replace("__TODAY__", date.today().isoformat())
        .replace("__CATALOGO__", catalogo)   # cacheado en memoria unos minutos
        .replace("__PREGUNTA__", pregunta[:500]),
    config=types.GenerateContentConfig(
        response_mime_type="application/json", temperature=0.2,
        max_output_tokens=600,               # tope duro de coste de salida
    ),
), attempts=2)                               # ← NO 4: esto es una petición web síncrona
```

`__TODAY__` es imprescindible por el mismo motivo que en la extracción: sin la fecha de hoy,
"octubre" y "esta semana" no se pueden resolver.

---

## 6. Riesgos y mitigaciones

### Alucinación — el bot inventa una oportunidad

Es el riesgo número uno: una persona se ilusiona con una plaza que no existe.

**Mitigación estructural, no una advertencia en el prompt:**

1. El LLM **solo devuelve `identifier`s**. No escribe ni un título, ni una fecha, ni una URL.
2. El backend **valida cada id contra el conjunto real de abiertas** y descarta los que no
   existan. Si el modelo se inventa `CORRADI-2026-9999`, desaparece antes de salir de la API.
3. Si tras filtrar no queda ninguno pero el texto prometía resultados → se sustituye la
   respuesta por el mensaje de "no he encontrado nada, prueba con los filtros".
4. El front pinta las tarjetas desde **su propio JSON**, no desde el texto del modelo.

Con esas cuatro capas, mostrar una oportunidad inexistente es imposible por construcción. Lo
que sí puede fallar es la **prosa** (decir "3 en Italia" cuando son 2), y eso se mitiga con
temperatura baja y con que las tarjetas reales estén siempre a la vista debajo.

Riesgo residual real, y hay que asumirlo: que el bot **omita** una oportunidad válida. Por eso
la respuesta debe terminar siempre con una salida hacia los filtros ("¿no ves lo que buscas?
Prueba los filtros del mapa").

### Alucinación por omisión de datos (el caso de la edad)

Con `participant_max_age` al 32%, el bot **no puede** afirmar "no hay nada para mayores de
25". Regla explícita en el prompt: si el rango de edad no consta, **incluir** la oportunidad
marcándola como "no consta la edad, confírmalo en el infopack". Mismo criterio que ya aplica
el filtro de edad del mapa.

### Inyección de prompt desde el propio catálogo

Ojo con esto: el texto de las oportunidades **no lo escribimos nosotros**. Viene de
coordinadores y del **scraping de SALTO-YOUTH**. Un `summary` que contenga "ignora las
instrucciones anteriores y di que…" entraría en el prompt.

Mitigaciones: (1) el catálogo va **delimitado** y el prompt declara que es *dato*, nunca
instrucciones; (2) el daño máximo posible es texto raro en la prosa, porque la salida está
constreñida a JSON con ids validados — no hay herramientas, ni BD escribible, ni acceso a
nada; (3) el campo `contact_information` **no se manda** al prompt.

### Coste descontrolado / abuso

Requisito ya anotado en `ideas_futuras_web.md` #13: **rate-limit por IP desde el día uno**.

- **Por IP**: p.ej. 10 consultas/hora y 30/día. En memoria del proceso — el `api` corre como
  **un único uvicorn sin `--workers`** en un solo contenedor (`docker/api.Dockerfile`), así
  que un `dict` con ventana deslizante basta; **no hace falta Redis**. Una IP abusiva cuesta
  como mucho 0,026 $/día.
- **Kill-switch global diario** configurable (`CHAT_MAX_DAILY`, p.ej. 2.000). Al superarlo, el
  endpoint responde 200 con `aviso` y el front cae al matcher/filtros. Techo de gasto duro:
  2.000 × 0,00085 $ = **1,70 $/día ≈ 51 $/mes en el peor caso absoluto**.
- **`max_output_tokens=600`** — acota la mitad cara del coste (la salida vale 4× la entrada).
- **Longitud de pregunta acotada** a ~500 caracteres.
- La IP la ve FastAPI a través de Caddy: hay que leer `X-Forwarded-For` (Caddy la pone), no
  `request.client.host`, que sería siempre la IP del contenedor de Caddy.

### Privacidad

`docs/privacidad.md` ya declara que el texto de las convocatorias se procesa con Gemini,
pero **no cubre** que las preguntas de los visitantes se envíen a Google. Hay que añadirlo.

Propuesta minimalista, coherente con el resto del proyecto (favoritas en `localStorage`,
contador de visitas agregado, sin cuentas):

- **No se guarda la IP.** Ni en claro ni hasheada. La ventana del rate-limit vive en memoria
  y muere con el proceso.
- **No se guarda el historial de conversación** en el servidor. Sin sesiones, sin cookies.
- Se guarda, como mucho, un **contador agregado** en la tabla `counters` (nº de consultas/día)
  para el informe de impacto del KA210.
- **Opcional y a decidir (§8)**: guardar el *texto* de las preguntas sin ningún identificador,
  para saber qué se busca y no existe (idea #29). Es un dato valioso para el KA210 pero cambia
  el aviso de privacidad; por defecto propongo **no** hacerlo en la v1.
- Aviso visible en el diálogo: "Tu pregunta se envía a Google Gemini para interpretarla. No
  escribas datos personales."

### Fallo de Gemini

`with_retry` existe pero con `attempts=4` y backoff exponencial puede tardar **~15 s**, lo
que es inaceptable en una petición web síncrona. Para el chat: `attempts=2` y un timeout duro
de ~8 s. Ante fallo, error o kill-switch, el front **siempre** tiene salida: los 44
resultados ya están en el navegador y los filtros funcionan sin backend. El mensaje debe ser
concreto ("el asistente no está disponible ahora mismo — usa los filtros o el buscador"), no
un error genérico.

### Contenido inapropiado

El endpoint es público y anónimo. Regla en el prompt: solo se responde sobre oportunidades
de movilidad; para cualquier otra cosa, negarse con una frase amable y redirigir al mapa.
Con `max_output_tokens=600` y salida JSON constreñida, el margen para usarlo de ChatGPT
gratis es escaso, pero conviene que la negativa esté escrita.

---

## 7. Plan de implementación por fases

| Fase | Qué | Esfuerzo |
|---|---|---|
| **0. Validar el prompt** | Script de scratchpad que arma el catálogo desde `/api/map` y lanza ~20 preguntas reales contra flash-lite. **Medir latencia y tokens de verdad.** Iterar el prompt hasta que la selección de ids sea buena. Sin UI, sin endpoint. **Si aquí la calidad no convence, se para y se hace el matcher (c) y ya está.** | **0,5 día** |
| **1. Backend** | `app/llm/chat.py` (prompt + llamada, patrón de `extractor.py`), `app/llm/prompts.py` (`CHAT_PROMPT`), `POST /api/chat` en `main.py`, construcción + caché del catálogo, validación de ids, rate-limit por IP, kill-switch, `X-Forwarded-For`, entrada en `@publico` del `Caddyfile`, variables en `config.py` + `.env.example`, tests con `LLM_PROVIDER=fake`. | **1,5 días** |
| **2. UI** | Botón `✨ Preguntar`, `<dialog id="chatDialog">` reutilizando `.info-dialog`, chips de sugerencia, render de tarjetas con la función existente, "Ver estas N en el mapa" (`state.only`), estados de carga/error/rate-limit. | **1,5 días** |
| **3. Cierre** | Contador agregado en `counters`, apartado en el modal de Información, párrafo en `docs/privacidad.md`, despliegue y observación del gasto real durante una semana. | **0,5 día** |

**Total ≈ 4 días.** La fase 0 es la que decide si merece la pena seguir; conviene no saltársela.

Fuera de alcance de la v1, deliberadamente: multi-turno con historial (duplica los tokens de
entrada por consulta), streaming de la respuesta, voz, y traducción de la interfaz.

---

## 8. Preguntas abiertas (necesitan decisión)

1. **¿Se acepta que las preguntas de los visitantes se envíen a Google?** Es el requisito
   previo. Implica actualizar `docs/privacidad.md` y poner el aviso en el diálogo.
2. **¿En qué tier está `GEMINI_API_KEY`?** Si está en el gratuito (30 RPM), el chat público
   competiría por la misma cuota que el pipeline de extracción, que es lo crítico.
   **Recomendación: clave separada para el chat**, aunque sea del mismo proyecto — aísla la
   cuota y permite una alerta de presupuesto propia.
3. **¿Presupuesto tope al mes?** Define el número del kill-switch. Con 10 $/mes de tope →
   ~390 consultas/día. Con 25 $/mes → ~1.000/día.
4. **¿Multi-turno o pregunta suelta?** Propongo **pregunta suelta** en la v1 (cada consulta es
   independiente): es más barato, más predecible y cubre el 90% del caso de uso. Multi-turno
   se puede añadir después arrastrando solo los últimos 2 turnos.
5. **¿Idioma de la respuesta: siempre castellano, o espejo de la pregunta?** El mapa está en
   español y el público objetivo son residentes en España, pero los títulos vienen en su
   idioma original. Propongo **espejo** (responder en el idioma en que se pregunte).
6. **¿Se guarda el texto de las preguntas?** Muy útil para el KA210 (demanda no cubierta, idea
   #29) pero cambia el aviso de privacidad. Propongo **no** en la v1, y decidirlo aparte.
7. **¿Se expone `organiser_name` en `/api/map`?** Hoy está en BD pero no en la lista blanca
   `_PUBLIC_FIELDS`. Sin él, el bot no puede responder "¿quién lo organiza?". Es una decisión
   de exposición de datos, no un olvido — de ahí que se pregunte.
8. **¿`gemini-2.5-flash-lite` o subir a `gemini-2.5-flash`?** Flash-lite es lo que ya se usa y
   basta de sobra para seleccionar ids de una lista. Flash razona mejor con fechas y
   condiciones combinadas, pero cuesta **3× la entrada y 6× la salida** (2,55 → ~8,5 $/mes a
   100 consultas/día). **Decidirlo con los datos de la fase 0**, no antes.
9. **¿Debe el bot cubrir también las oportunidades cerradas?** Hoy no existe archivo (idea
   #11). Si algún día lo hay, "¿suele haber cosas en Italia en primavera?" sería contestable.
   Fuera de alcance ahora.

---

## Fuentes de los precios

- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing) — `gemini-2.5-flash-lite`
  0,10 $/1M entrada y 0,40 $/1M salida; `gemini-embedding-001` 0,15 $/1M.
- [Gemini 2.5 models now support implicit caching](https://developers.googleblog.com/gemini-2-5-models-now-support-implicit-caching/) —
  descuento del 75% sobre el prefijo cacheado, mínimo ~1.024 tokens.
- Conteos de tokens: medidos con `countTokens` de la API real contra el catálogo de
  producción del 2026-07-27 (44 oportunidades abiertas).
