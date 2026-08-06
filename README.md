# CORRADI-BOT

**Difusión automática de oportunidades Erasmus+ para jóvenes, sobre Telegram.**

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async%20API-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791)
![Gemini](https://img.shields.io/badge/LLM-Gemini%202.5-8E75B2)
![Docker Compose](https://img.shields.io/badge/deploy-Docker%20Compose-2496ED)

Proyecto Erasmus+ **KA210-YOU** (Proactive Future + LIFE Rumanía + DreamTeam Grecia).
Convierte las oportunidades de movilidad juvenil que hoy circulan sueltas y a mano (Kosmos,
Instagram, grupos de WhatsApp...) en una **base de datos estructurada** que se difunde sola,
sin intervención humana en el día a día.

---

## Índice

- [Idea central](#idea-central-separar-el-cerebro-de-la-boca)
- [Flujo de datos](#flujo-de-datos)
- [El bot: @corradi_erasmus_bot](#el-bot-corradi_erasmus_bot)
- [Anti-abuso](#anti-abuso)
- [Stack](#stack-alineado-con-la-propuesta-financiada)
- [Estructura del repo](#estructura-del-repo)
- [Puesta en marcha](#puesta-en-marcha)
- [Producción (AWS EC2)](#producción-aws-ec2--ya-desplegado)
- [Configuración (`.env`)](#configuración-env)
- [Reenvío a WhatsApp (bot de difusión)](#reenvío-a-whatsapp-bot-de-difusión)
- [Resumen semanal](#resumen-semanal)
- [Bandera de país](#bandera-de-país-en-cada-post)
- [Calidad de extracción](#calidad-de-extracción--aprendido-con-mensajes-reales)
- [Qué está aparcado (WhatsApp Business API)](#qué-está-aparcado-whatsapp-business-api)
- [Pendiente / siguientes bloques](#pendiente--siguientes-bloques)

---

## Idea central: separar el "cerebro" de la "boca"

```mermaid
flowchart LR
    subgraph Entrada
        C[Coordinador] -->|pega el texto tal cual, sin pedir acceso| BOT[Bot Telegram\n@corradi_erasmus_bot]
    end

    subgraph "Cerebro (agnóstico de canal)"
        BOT --> LLM[Gemini\nclasifica + extrae campos]
        LLM -->|no es oportunidad| REPLY1[Responde al coordinador]
        LLM -->|oportunidad real| DEDUP{¿Duplicada?\nhash + pgvector}
        DEDUP -->|sí| REPLY2[Avisa: ya existe]
        DEDUP -->|no| PREVIEW[Vista previa\nEnviar / Modificar / Cancelar]
        PREVIEW -->|Enviar| DB[(PostgreSQL\nprojects)]
    end

    subgraph "Boca (difusión)"
        DB --> PUB[Canal de Telegram\n@erasmuscorradi]
        DB --> SUM[Resumen diario\nabiertas / vencidas]
    end
```

- **Cerebro**: captura → clasificación + extracción con LLM → deduplicación → BD estructurada.
  Es el activo que escala a otros países y canales; no sabe nada de Telegram en sí.
- **Boca** (adaptadores enchufables): hoy **Telegram**, con confirmación del propio
  coordinador antes de publicar. Mañana: web/PWA, app móvil, y WhatsApp si vuelve a ser
  viable (ver [más abajo](#qué-está-aparcado-whatsapp)).

**Lanzamiento: 100% Telegram.** Los Canales de difusión de WhatsApp no tienen API de
publicación (solo se puede publicar a mano, incluso siendo admin), así que WhatsApp queda
aparcado para esta fase.

## Flujo de datos

1. Un **coordinador** le pega al bot el mensaje de una oportunidad tal cual lo tenga (Kosmos,
   Instagram, lo que sea — no hace falta limpiarlo ni pedir acceso antes). **Una oportunidad
   por mensaje** (si el texto trae varios proyectos a la vez, el bot pide que se separen).
2. Gemini decide si es una oportunidad real y extrae los campos (título, tipo, fechas, país,
   deadline, formulario…). Si no trae deadline explícita, se estima **+5 días** (**+2 días**
   si el mensaje dice "última hora"/"últimas plazas"). Si una fecha no trae año, se asume el
   próximo futuro (nunca en el pasado).
3. **Control de plazo:** si la fecha límite que trae el mensaje **ya ha pasado**, la
   oportunidad no se publica: el bot responde a quien la mandó avisándole de que está fuera
   de plazo (se registra como `expired` en `submissions`). Y si la deadline final cae **a más
   de 3 meses vista** (`MAX_DEADLINE_MONTHS`), tampoco se publica — suele ser un año mal
   inferido (p.ej. "17/07" sin año, procesado después del 17 de julio) — se registra como
   `deadline_too_far` y se pide revisar el mensaje.
4. Deduplicación: hash exacto (título+país+fecha) + similitud coseno (pgvector) sobre el
   embedding del mensaje completo.
5. El bot muestra una **vista previa** de cómo quedaría publicada y el coordinador decide:
   **✅ Enviar**, **✏️ Modificar** algo (en lenguaje natural: "cámbiale la fecha de fin al
   20") o **❌ Cancelar**. Nada se guarda ni se publica hasta que se pulsa Enviar.
6. Al confirmar, se guarda en `projects` con un identificador legible (`CORRADI-2026-0001`)
   — es **interno**, no se muestra al coordinador ni en el canal; solo se usa en BD/API — y
   se publica en el canal de Telegram [@erasmuscorradi](https://t.me/erasmuscorradi).
7. Al instante, el bot dedicado de difusión reenvía la oportunidad por DM en formato
   WhatsApp, lista para copiar y pegar (ver [Reenvío a WhatsApp](#reenvío-a-whatsapp-bot-de-difusión)).
8. Cada día a las 20h se expira lo vencido (sin mandar ningún mensaje — ver la misma sección).

No hay paso de **aprobación por un tercero** (moderación/admin) antes de publicar: si el LLM
la valida como oportunidad real, no es un duplicado y el propio coordinador confirma el
envío, sale al canal directamente. El coordinador puede después editarla o eliminarla con
`/editarmisproyectos` (ver [más abajo](#el-bot-corradi_erasmus_bot)).

## El bot: `@corradi_erasmus_bot`

No hace falta memorizar comandos: **basta con pegarle el texto de la oportunidad como
mensaje normal** y el bot hace el resto (clasificar, extraer, deduplicar, publicar).

### Acceso — abierto por defecto

Cualquiera puede escribirle al bot y mandar oportunidades directamente, **sin pedir permiso
antes**. El único filtro es reactivo: si Pachu (@pachums97) detecta un problema con alguien,
se le bloquea a mano; y el propio bot bloquea solo a quien haga spam (ver
[Anti-abuso](#anti-abuso)).

| Comando | Qué hace |
|---|---|
| `/start` | Explica cómo funciona el bot |
| `/ayuda` | Reglas de uso, enlace al canal y al mapa |
| `/editarmisproyectos` | Tus oportunidades **abiertas**: botones para editarlas (en lenguaje natural) o eliminarlas (pide confirmación) |
| `/historicomisproyectos` | Todo lo que has publicado, con su estado (🟢 abierta / ⚫ eliminada / 📅 caducada), solo lectura |

Editar o eliminar una oportunidad solo cambia la base de datos (y por tanto la web/mapa): el
mensaje ya publicado en el canal se queda como estaba, eso no se puede deshacer. No hay
comandos de administración en el bot — bloquear o desbloquear a alguien se hace directamente
en la base de datos (tabla `blocked_users`), no vía un comando expuesto. Los **admins**
(`ADMIN_TELEGRAM_IDS`) no tienen límite diario ni pueden auto-bloquearse por spam.

## Anti-abuso

Para que el canal no se llene de spam ni de mensajes fuera de sitio:

- **Máximo `MAX_DAILY_OPPORTUNITIES` oportunidades al día por persona** (3 por defecto), salvo
  admins (`ADMIN_TELEGRAM_IDS`), que no tienen límite. Al superarlo, el bot responde pidiendo
  que se reintente al día siguiente — no llega a llamar al LLM, así que tampoco cuesta nada.
- **Sistema de 2 avisos**: si un mensaje no es una oportunidad, el bot avisa (⚠️). Si el
  *siguiente* mensaje de esa misma persona **tampoco** lo es, se bloquea el acceso
  automáticamente y se avisa a los admins por Telegram — el bloqueo es indefinido, se
  levanta a mano en la base de datos. Cualquier envío bueno de por medio resetea el contador.
  El umbral es `SPAM_BLOCK_THRESHOLD` (2 por defecto). Los admins tampoco están sujetos a
  este sistema.
- **Todo envío queda registrado** en la tabla `submissions` (creada, duplicada, no-oportunidad,
  límite superado, error), con el ID de Telegram de quien lo mandó — es la base de datos que
  usan las dos reglas anteriores, y también sirve de auditoría si hace falta revisar quién
  mandó qué.

## Stack (alineado con la propuesta financiada)

| Pieza | Uso |
|---|---|
| **PostgreSQL 16 + pgvector** | Catálogo de oportunidades + dedup semántico por embedding |
| **FastAPI** | API pública de lectura: mapa (`/api/map`), catálogo, contador de visitas (`/api/visit`) |
| **Caddy** | Proxy inverso público con HTTPS (Let's Encrypt); filtra rutas |
| **python-telegram-bot** | Captura (DM) y publicación (canal) |
| **Google Gemini** (`gemini-2.5-flash-lite` + `gemini-embedding-001`) | Clasificación, extracción de campos, embeddings |
| **Docker Compose** | Mismo despliegue en local y en EC2 |

> Redis se retiró del stack: estaba configurado pero no se usaba en el código.

## Estructura del repo

```
corradi/
├── docker-compose.yml          # db (pgvector) + api + bot + caddy
├── db/migrations/               # esquema (0001) + submissions/tracking (0002)
├── docker/                     # api.Dockerfile, bot.Dockerfile
├── run_bot.py                  # entrypoint del bot
├── terraform/                  # EC2 t4g.small + Docker (IaC, fase 0 de despliegue)
├── docs/
│   ├── mensajes_ejemplo.md     # corpus real (13 mensajes), para medir calidad de extracción
│   ├── privacidad.md
│   └── archive/                # guías de WhatsApp (Twilio/Meta Cloud), aparcadas
├── tests/                      # pytest, no necesitan BD ni claves (LLM_PROVIDER=fake)
└── app/
    ├── config.py                # toda la config vía variables de entorno (.env)
    ├── domain/
    │   ├── project.py           # parseo de campos del LLM, hash de dedup, red de seguridad de fechas
    │   └── project_type.py      # enums (YOUTH_EXCHANGE, TRAINING_COURSE, VOLUNTEERING)
    ├── db/
    │   ├── pool.py               # pool async (psycopg3) + adaptador pgvector
    │   └── repository.py         # oportunidades + lista blanca + solicitudes + tracking de envíos
    ├── llm/
    │   ├── prompts.py             # prompt de clasificación + extracción
    │   ├── extractor.py           # llama a Gemini, normaliza la respuesta
    │   ├── embeddings.py          # embeddings para dedup semántico
    │   ├── retry.py               # reintentos con backoff ante 503 de Gemini
    │   └── fake.py                 # extracción heurística para dry-run (LLM_PROVIDER=fake)
    ├── pipeline.py                # clasifica → deduplica → guarda → publica → handoff (agnóstico de canal)
    ├── publisher/
    │   ├── telegram_publisher.py   # formatea y publica en el canal
    │   ├── handoff.py               # despachador de handoff (hoy: 'telegram' -> whatsapp_relay.py)
    │   ├── whatsapp_relay.py        # bot dedicado que reenvía cada oportunidad al admin por DM (ver abajo)
    │   ├── whatsapp_twilio.py       # ⚠️ aparcado
    │   └── whatsapp_cloud.py        # ⚠️ aparcado
    ├── bot/telegram_bot.py         # comandos + captura de mensajes
    ├── api/
    │   ├── main.py                  # FastAPI: catálogo/búsqueda
    │   └── twilio_webhook.py        # ⚠️ aparcado (entrada por WhatsApp)
    └── scheduler/
        ├── daily_summary.py         # solo expira lo vencido (ya no manda ningún mensaje)
        └── weekly_summary.py        # resumen semanal de los domingos
```

## Puesta en marcha

### Todo en Docker (igual en local y en EC2)

```bash
cp .env.example .env     # rellena TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, ADMIN_TELEGRAM_IDS…
make up                  # docker compose up -d --build
make logs
```
- API en http://localhost:8000  (`/health`, `/opportunities`, `/opportunities/{id}`)
- La BD se inicializa con los scripts de `db/migrations/` (pgvector + tablas) — pero
  **solo la primera vez** que se crea el volumen de Postgres. Si añades una migración nueva
  sobre una BD que ya existe, aplícala a mano:
  ```bash
  docker exec -i corradi-db psql -U corradi -d corradi < db/migrations/000X_nombre.sql
  ```

Tras cambiar `.env` (token, canal…), reconstruye y recrea el contenedor afectado:
```bash
docker compose build bot && docker compose up -d --force-recreate bot
```

### Desarrollo de la app en local (BD en Docker)

```bash
make dev-db              # solo Postgres
make install
make bot                 # bot de captura
make api                 # API con reload
make summary             # resumen diario (probar a mano)
```

### Sin BD ni claves (dry-run)

```bash
make test                # tests con LLM_PROVIDER=fake (extracción heurística)
make demo                # flujo completo offline
make seed                # carga ejemplos en la BD (necesita 'make dev-db')
```

## Producción (AWS EC2) — YA DESPLEGADO

El bot corre **24/7 en una EC2 t4g.small** (Ubuntu 24.04 ARM), provisionada con el Terraform
de `terraform/`. Todo el stack (db + api + bot + caddy) corre en Docker Compose. El mapa es
**público** vía Caddy (HTTPS con Let's Encrypt) en el dominio propio; la API no publica puerto
al exterior (Caddy filtra las rutas permitidas).

| Dato | Valor |
|---|---|
| Mapa público | **https://mapa.proactivefuture.eu** |
| Instancia / IP elástica | `i-0af46b60fc0458333` · `52.49.142.64` (`eu-west-1`) |
| Acceso a la instancia | **AWS SSM Session Manager** (no hay puerto 22 abierto) |
| Ruta del proyecto | `/opt/corradi` |
| Coste | **0 € hasta 31-dic-2026** (free trial), luego ~17-19 €/mes |

**Resiliencia**: los contenedores usan `restart: unless-stopped` y Docker arranca al bootear,
así que todo vuelve solo tras un reinicio o si un contenedor se cae. Los cron (expiración
diaria 20:00, resumen semanal domingos 20:30, backup de BD) están en el `crontab` de la
instancia, en hora de Madrid.

> ⚠️ **No arranques el bot en local mientras el de AWS esté vivo**: los dos competirían por
> el mismo token de Telegram (solo un proceso puede hacer *polling*) y fallarían de forma
> intermitente. El entorno local queda parado (sirve de respaldo).

### Acceso a la instancia (SSM, sin puerto 22)

El SG solo abre 80/443 (Caddy). Para entrar se usa **SSH sobre SSM** (el agente SSM tuneliza;
requiere `aws` CLI configurado + `session-manager-plugin` + tu clave en la instancia):

```bash
IID=i-0af46b60fc0458333
SSM='ssh -o ProxyCommand="aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters portNumber=%p --region eu-west-1"'
eval $SSM ubuntu@$IID            # entra a la instancia
# ver/operar:
#   docker ps ; docker logs corradi-bot --tail 50 -f
#   docker exec corradi-db psql -U corradi -d corradi -c "SELECT identifier,title,status FROM projects;"
```

### Flujo de edición y despliegue

1. **Editas en local** (`app/…`, `app/api/static/mapa.html`, …).
2. **Pruebas**: `make test` (o `make demo` offline sin claves).
3. **Commit + push** a `github.com/tech809/corradi` (`git push`).
4. **Subes a AWS y reconstruyes** el/los servicio(s) afectados, por SSM:
   ```bash
   rsync -a -e "$SSM" --exclude .env --exclude .git --exclude '__pycache__' \
     --exclude '.pytest_cache' --exclude 'terraform/.terraform' \
     ./ ubuntu@$IID:/opt/corradi/
   eval $SSM ubuntu@$IID 'cd /opt/corradi && docker compose up -d --build bot api'
   ```
   - **api/bot**: el código va horneado en la imagen → hay que **rebuild** (`--build`).
   - **mapa.html**: lo sirve la api → también necesita rebuild de `api`.
   - **Caddyfile**: es un bind-mount de un fichero → tras cambiarlo, **reiniciar** el
     contenedor (`docker restart corradi-caddy`), no basta rsync (rompe el inodo del mount).

> 🔴 **Excluye SIEMPRE `.env` del rsync** (`--exclude .env`). Sin ello, el `.env` local pisa
> el de producción (que tiene `MAP_DOMAIN`, `MAP_PUBLIC_URL`, etc. propios). Si pasa, se puede
> recuperar del contenedor en marcha: `docker exec corradi-api env`.

## Configuración (`.env`)

Variables imprescindibles para el lanzamiento actual (ver `.env.example` para el resto):

| Variable | Para qué |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot (@corradi_erasmus_bot) |
| `TELEGRAM_CHANNEL_ID` | Canal de difusión, formato `-100...` (hoy: `@erasmuscorradi`) |
| `ADMIN_TELEGRAM_IDS` | IDs numéricos de Telegram con permisos de admin, separados por coma |
| `GEMINI_API_KEY` | Clave de Google Gemini |
| `HANDOFF_MODE` | `telegram` (por defecto): reenvía cada oportunidad al bot de difusión — ver `WHATSAPP_RELAY_BOT_TOKEN` |
| `WHATSAPP_RELAY_BOT_TOKEN` | Token del bot dedicado @corradi_erasmus_whatsapp_bot (DM a `ADMIN_TELEGRAM_IDS` con el texto listo para copiar y pegar en el canal de difusión de WhatsApp) |
| `DEFAULT_DEADLINE_DAYS` | Días de margen si no hay deadline explícita en el texto (5 por defecto) |
| `LAST_MINUTE_DEADLINE_DAYS` | Igual, pero si el mensaje dice "última hora"/"últimas plazas" (2 por defecto) |
| `MAX_DEADLINE_MONTHS` | Solo se aceptan oportunidades cuya deadline caiga dentro de estos meses (3 por defecto; red de seguridad ante años mal inferidos) |
| `MAP_DOMAIN` | Dominio del mapa público; Caddy pide el certificado HTTPS para este nombre (vacío = HTTP sin TLS) |
| `MAP_PUBLIC_URL` | URL pública del mapa; también la base del enlace corto que lleva cada oportunidad en el texto de WhatsApp |
| `DEDUP_THRESHOLD` | Umbral de similitud coseno para considerar duplicado (0.88 por defecto) |
| `TELEGRAM_CHANNEL_USERNAME` | Username público del canal (sin @); enlaza cada oportunidad a su post original (mapa, resumen semanal) |
| `MAX_DAILY_OPPORTUNITIES` | Máximo de oportunidades que puede crear un coordinador al día (3 por defecto) |
| `SPAM_BLOCK_THRESHOLD` | Mensajes seguidos que no son oportunidad antes de bloquear automáticamente (2 por defecto: aviso + bloqueo) |

### Configurar el canal de difusión (referencia)

1. Añade al bot como **administrador** del canal, con permiso "Publicar mensajes".
2. Saca el `chat_id` numérico (para un canal público `@usuario`):
   ```
   GET https://api.telegram.org/bot<TOKEN>/getChat?chat_id=@usuario
   ```
3. Ponlo en `.env` como `TELEGRAM_CHANNEL_ID` (formato `-100...`).

## Reenvío a WhatsApp (bot de difusión)

WhatsApp no tiene API accesible para el canal de difusión real (no es negocio, es un canal
normal) — así que el flujo es manual a propósito: en cuanto se publica una oportunidad
(venga de donde venga: bot de Telegram, panel web `/publicar`, backlog de SALTO-YOUTH — las
tres pasan por `pipeline.commit()`), el bot dedicado **@corradi_erasmus_whatsapp_bot**
(token propio en `WHATSAPP_RELAY_BOT_TOKEN`, separado del bot principal) le manda por DM a
cada `ADMIN_TELEGRAM_IDS` el texto ya formateado, listo para copiar y pegar. Sin foto — el
canal de difusión de WhatsApp es solo texto — así que bandera y categoría (que en el canal
de Telegram van en la imagen del post, ver `opportunity_card.py`) se escriben aquí en vez de
omitirse. Formato:

```
🇦🇹 *PILCROW*
🎓 Training Course
🏷️ Temática: bienestar, naturaleza, actividades al aire libre, aprendizaje no formal, resiliencia
📍 Rettenegg, Austria
🗓️ 21-29 sept

Oportunidad de curso de formación Erasmus+ en Rettenegg, Austria, para 8 participantes de 18 a 30 años.

Form: https://forms.gle/Ran8RWbvBNcMw9kb9
Mapa: https://mapa.proactivefuture.eu/2026-0107

⏳ Fecha límite: 2026-08-06 (estimada) (cierra hoy)
```

Cada bloque (cabecera, resumen, Infopack/Form/Contacto/Mapa, fecha límite) va separado por
una línea en blanco. Infopack/Form/Contacto/Mapa son líneas independientes que solo
aparecen si hay dato real (nunca "Infopack: -" para rellenar a mano). El resumen se recorta
a ~3 líneas (`_cap_summary`, corta en frase completa) aunque el original sea más largo —
tope real en código, no solo en el prompt del extractor.

Cada admin tiene que haberle mandado `/start` al bot al menos una vez: la API de Telegram no
deja que un bot escriba primero a nadie que no lo haya hecho. Si `WHATSAPP_RELAY_BOT_TOKEN`
está vacío, `whatsapp_relay.py` no hace nada (no revienta el resto del pipeline).

> Hasta el 4-ago-2026 este reenvío iba a un grupo de Telegram y, además, un cron aparte
> (`daily_summary.py`) mandaba cada noche a las 20h un resumen de lo publicado ese día.
> Se retiró ese resumen sin sustituto: con el reenvío al instante, un digest al final del
> día dejó de aportar nada. `daily_summary.py` sigue existiendo (mismo cron, mismo nombre)
> pero ahora solo expira las oportunidades cuyo plazo ya pasó — no manda ningún mensaje.

## Mapa público

Mapa interactivo de las oportunidades **abiertas**, servido por la propia API en `GET /mapa`
(página autocontenida en `app/api/static/mapa.html`, Leaflet + teselas de CARTO/OpenStreetMap,
sin claves de API ni coste). `MAP_PUBLIC_URL` es también la base del enlace corto que
lleva cada oportunidad en el texto de WhatsApp (ver "Reenvío a WhatsApp").

**Qué hace:** pines por categoría (Youth Exchange azul · Training Course amarillo · ECS verde),
filtros agrupados en un solo panel — texto, categoría, edad, país, fechas
(meses o rango de deadline) y "cierran pronto" (≤7 días) —, lista lateral sincronizada con el
mapa (clic en tarjeta → vuela al pin y abre su ficha), badge "🆕 Nuevo" en lo publicado en las
últimas 24h, badge de urgencia
("Cierra hoy", "Cierra en 3 días"), botón 🔗 para compartir cada ficha, footer con
estadísticas de visitas y enlaces a inscripción, infopack y post original del canal.
Responsive; **siempre en modo claro** (a propósito: no sigue el modo oscuro del sistema, para
mantener consistente la lectura de los colores por tipo).

### Coordenadas

`app/geo.py` geocodifica en dos escalones y guarda el resultado en `projects.latitude/longitude`
(columnas que ya existían desde la migración inicial), así que cada ficha se geocodifica **una
sola vez**, al crearse:

1. **Ciudad exacta** vía Nominatim (OpenStreetMap): gratis, sin clave. Si el `location` es
   demasiado específico ("Manjirón, Sierra Norte de Madrid") reintenta con la primera parte.
2. **Centro del país** si no hay ciudad, si Nominatim no encuentra nada o si falla la red.
   Esos pines se marcan en la ficha como "Ubicación aproximada (país)".

Si todo falla, la oportunidad se publica igual en el canal; solo se queda fuera del mapa.

```bash
make backfill-geo   # geocodifica las fichas creadas antes de existir el mapa (1 req/s)
```

### Exposición pública y seguridad

La API **no** se expone directamente. Delante va **Caddy** (`docker/Caddyfile`), que da HTTPS
automático con Let's Encrypt y actúa de filtro:

| Decisión | Por qué |
|---|---|
| El contenedor `api` ya no publica el puerto 8000 al host | Todo el tráfico público entra por Caddy |
| Caddy solo deja pasar `/`, `/mapa`, `/corradi-erasmus`, `/og.png`, `/api/map`, `/api/visit`, `/health` y `/opportunities*` | Cualquier otra ruta devuelve 404 |
| El webhook de Twilio solo se monta si `HANDOFF_MODE` es de WhatsApp | Con la API pública y `TWILIO_VALIDATE_SIGNATURE=false`, dejarlo montado permitiría a cualquiera hacer POST y colar oportunidades en el canal. Hoy `HANDOFF_MODE=telegram` (reenvío por bot dedicado, no WhatsApp Business API), así que la ruta ni existe |
| La API serializa con **lista blanca** de campos (`_PUBLIC_FIELDS`) | `submitted_by`, `submitted_by_id`, `raw_message`, `hash` y `embedding` no salen nunca. Al ser lista blanca, una columna nueva no se filtra sola |

Variables: `MAP_DOMAIN` (dominio para el certificado) y `MAP_PUBLIC_URL` (lo que se enlaza en
el resumen). En Terraform, `expose_web = true` abre 80/443.

> El puerto 80 es imprescindible además del 443: Let's Encrypt lo usa para validar el dominio.

## Resumen semanal

`app/scheduler/weekly_summary.py` publica los domingos (20:30, media hora después del
diario) cuántas oportunidades nuevas se publicaron esa semana, cuántas siguen abiertas ahora
mismo, y el top de países y temáticas de lo publicado esa semana:

```
📊 Resumen semanal — 20 de julio al 21 de julio de 2026

✅ 6 oportunidades nuevas publicadas esta semana
☀️ 6 abiertas ahora mismo

🌍 Top países: 🇪🇸 España (2) · 🇩🇪 Alemania (2) · 🇧🇬 Bulgaria (1) · 🇮🇹 Italia (1)
🏷️ Top temáticas: Intercambio juvenil (3) · Training course (2) · Voluntariado (1)
```

```bash
crontab -l   # 30 20 * * 0 docker exec corradi-bot python -m app.scheduler.weekly_summary
make weekly-summary   # probarlo a mano
```

## Bandera de país en cada post

Cada oportunidad publicada en el canal lleva la **bandera del país** delante del título
(a partir de `country_code`, sin tabla que mantener — es una fórmula Unicode). Ver `_flag()`
en `app/publisher/telegram_publisher.py`.

## Calidad de extracción — aprendido con mensajes reales

`docs/mensajes_ejemplo.md` recoge un corpus real (13 mensajes) usado para validar el
extractor. Dos hallazgos de la última ronda de pruebas:

- **Fechas sin año** (p.ej. "19–27 septiembre"): el LLM podía inferir un año equivocado o
  pasado. **Corregido**: el prompt ahora recibe la fecha de hoy (`app/llm/prompts.py` +
  `extractor.py`) y, además, `app/domain/project.py` (`_future()`) empuja al año siguiente
  cualquier fecha que salga en el pasado — red de seguridad, porque estas son siempre
  convocatorias a futuro.
- **Un mensaje, varias oportunidades**: algunos coordinadores mandaban 2-3 proyectos
  distintos en un solo texto. Se ha decidido que **esto no debe ocurrir**: cada oportunidad
  se manda en su propio mensaje. Como red de seguridad, si aun así llega un texto con varias
  oportunidades (Gemini a veces lo detecta y devuelve una lista en vez de un objeto), el bot
  no falla: responde pidiendo que se reenvíen por separado, en vez de guardar una ficha
  incompleta o dar un error críptico.

## Qué está aparcado (WhatsApp Business API)

El canal de difusión de WhatsApp real no tiene API accesible, así que la difusión de verdad
sigue siendo copiar-pegar a mano (ver "Reenvío a WhatsApp" arriba). Lo que SÍ es API oficial
de WhatsApp Business (mensajería automática 1:1, no el canal de difusión) sigue aparcado, sin
borrar y marcado como tal en sus docstrings:

- `app/publisher/whatsapp_twilio.py` / `whatsapp_cloud.py` — envío saliente (handoff)
- `app/api/twilio_webhook.py` — entrada por WhatsApp (funcionó en sandbox con Twilio)
- `docs/archive/whatsapp_twilio_setup.md` / `whatsapp_cloud_setup.md` — guías de alta

Para activarlo: cambiar `HANDOFF_MODE` a `whatsapp_twilio` o `whatsapp_cloud` y seguir
la guía correspondiente en `docs/archive/`.

## Pendiente / siguientes bloques

- **Aviso de facturación en AWS** (Budgets) para enero-2027, cuando acabe el free trial.
- **Backup fuera de la instancia**: hoy el `pg_dump` diario se guarda en la propia máquina
  (`/opt/corradi/backups`, rota 14 días). Endurecerlo copiándolo a S3 lo protegería ante la
  pérdida de la instancia.
- **Fuentes automáticas de oportunidades** (SALTO Training Calendar, agregadores de infopacks,
  portal ESC) — ver el análisis en `docs/fuentes_externas.md`.
- Catálogo web (Astro/React) + panel de moderación — A3 Fase 4.
- App móvil React Native + Expo — A3 Fase 5.
- Revisar si reactivar WhatsApp (chatbot 1:1 y/o handoff) más adelante.

> El análisis completo de infraestructura y coste (AWS vs Railway vs GCP/Oracle) está en
> [docs/infraestructura.md](docs/infraestructura.md).
