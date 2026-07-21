# Dónde correr CORRADI-BOT 24/7 — análisis de opciones y coste (2026-07-21)

## Qué hay que mantener vivo

- **Bot de Telegram** (`python-telegram-bot`, modo *polling*): proceso de larga duración, no
  vale una función serverless (necesita mantener la conexión abierta con la API de Telegram).
- **PostgreSQL 16 + pgvector**: hoy con ~10 filas, footprint mínimo.
- **FastAPI** (catálogo de solo lectura): opcional, muy ligera.
- **Cron**: resumen diario (20h) + semanal (domingos). Procesos cortos, no necesitan estar
  siempre corriendo, solo dispararse a su hora.
- **Redis**: configurado pero **no se usa en ningún sitio del código actual** (solo
  `REDIS_URL` reservado para el futuro). Se puede quitar del despliegue sin perder nada hoy.

Es una carga muy ligera — nada de esto necesita una máquina grande.

## ¿Se puede meter dentro de `proactive-web` (Supabase + Railway)?

Miré el repo (`proactive-be`/`proactive-fe`) para verlo con datos, no a ojo:

- **Backend en Railway** (Node/Express, confirmado por `.railwayignore` + URL de producción
  en `docs/deployment-guide.md`). Railway **no es serverless** — soporta procesos de larga
  duración sin problema, así que el bot técnicamente encajaría ahí como servicio aparte.
- **Pero la base de datos es Supabase**, y no es un Postgres "vacío": ya usan **Supabase
  Storage** y **Supabase Auth** de verdad (login con Google), no solo la BD.
- **Ya hay un bug de producción documentado** (`proactive-fe/docs/bug-troubleshooting.md`):
  *"Supabase free/starter plans have a connection pool limit (typically 60 connections)...
  connection pool exhausted"*. El pool ya está bajo presión con la web sola.

**Conclusión: no compartas la misma instancia de Supabase.** Añadir el bot (conexiones
persistentes de Postgres + pgvector) a un pool ya ajustado es jugar con la estabilidad de la
web real por ahorrarte un servicio aparte. Tu instinto de "igual es mezclar cosas que no
debiéramos" iba bien encaminado.

**Sí es razonable**, si quieres consolidar facturación, añadir el bot como **un servicio
nuevo dentro del mismo proyecto de Railway**, pero con **su propia base de datos** (desplegar
la misma imagen `pgvector/pgvector:pg16` que ya usas en local, como otro servicio de Railway
con volumen persistente) — sin tocar Supabase para nada. El coste no es "gratis porque ya
pagamos Railway": se paga aparte por el uso de estos servicios nuevos, aunque bajo la misma
cuenta.

## Comparativa de opciones

| Opción | Coste estimado/mes | Pros | Contras |
|---|---|---|---|
| **AWS EC2 t4g.small** (ya en `terraform/`) | **0 €** hasta dic-2026 (free trial), luego ~14-17 € | Ya comprometido en la propuesta financiada; Terraform ya escrito; una sola máquina, todo en Docker Compose igual que en local | Tras el trial, el más caro de los "de pago" |
| **Railway** (servicio nuevo + Postgres propio, sin tocar Supabase) | ~10-15 € (uso real, no plan fijo) | Misma cuenta que ya usáis; deploy muy simple desde Docker | No es gratis solo por "ya pagarlo"; hay que vigilar el pool si algún día se junta con algo más |
| **Fly.io** | ~5-8 € | Barato, deploy de imágenes Docker directo, sin tarjeta de crédito bloqueante | Menos "conocido" para el equipo; hay que gestionar 2 apps (bot + Postgres) |
| **GCP e2-micro (Always Free)** | **0 €** indefinido, si no se supera el límite gratuito | Gratis para siempre, no solo un trial | 1GB RAM es justo para todo junto; te desvías del AWS ya comprometido en la propuesta |
| **Oracle Cloud (Always Free, Ampere A1)** | **0 €** indefinido | El más generoso con diferencia (hasta 4 OCPU + 24GB RAM gratis para siempre) | Alta de cuenta más pesada (a veces piden reintentar por falta de capacidad ARM gratuita en la región) |

## Recomendación

1. **Ahora mismo**: aplicar el Terraform que ya existe (`terraform/`, EC2 t4g.small) — es
   gratis hasta finales de 2026, coincide con lo que ya está escrito en la propuesta
   financiada (así no complicas la justificación del proyecto ante Erasmus+), y el bot ya
   está listo para producción real.
2. **Quitar Redis** del `docker-compose.yml` de producción mientras no se use de verdad
   (ahorra RAM en la máquina, cero pérdida funcional hoy).
3. Si en algún momento preferís consolidar todo bajo Railway por comodidad de gestión,
   hacedlo como servicio + Postgres **propios**, nunca sobre la instancia de Supabase de
   `proactive-web`.
4. Oracle/GCP Always Free son la opción más barata en términos absolutos (0 €), pero solo
   tendría sentido si el coste fuera el único criterio — al estar ya AWS comprometido en la
   propuesta y con Terraform hecho, cambiar de proveedor ahora sería trabajo extra sin
   necesidad real.
