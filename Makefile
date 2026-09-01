.PHONY: up down logs build bot api summary weekly-summary top-projects backfill-geo backfill-details backfill-contacts backfill-embeddings install dev-db test demo seed

# ─── Docker (local = EC2: mismo compose) ───────────────────────────────────
up:        ## Levanta toda la pila (db, api, bot, caddy)
	docker compose up -d --build

down:      ## Para la pila
	docker compose down

logs:      ## Sigue los logs
	docker compose logs -f

build:     ## Reconstruye imágenes
	docker compose build

# ─── Ejecución local sin Docker (necesita Postgres y .env) ─────────────────
install:
	pip install -r requirements.txt

dev-db:    ## Solo Postgres en Docker (para desarrollar la app en local)
	docker compose up -d db

bot:
	python run_bot.py

api:
	uvicorn app.api.main:app --reload

summary:
	python -m app.scheduler.daily_summary

weekly-summary:
	python -m app.scheduler.weekly_summary

top-projects:
	python -m app.scheduler.top_projects

backfill-geo:  ## Geocodifica las fichas antiguas que aún no tienen coordenadas (mapa)
	python -m app.scheduler.backfill_geo

backfill-details:  ## Enriquece fichas antiguas con anuncio + infopack (usa llamadas LLM)
	python -m app.scheduler.backfill_details

backfill-contacts:  ## Sanea contact_information de fichas antiguas (simula; --apply para aplicar)
	python -m app.scheduler.backfill_contacts

backfill-embeddings:  ## Rellena el vector de dedup de fichas publicadas sin él (cuota 429)
	python -m app.scheduler.backfill_embeddings

scrape-salto:  ## Busca oportunidades nuevas de Training Course en SALTO-YOUTH y avisa por DM
	python -m app.scheduler.scrape_salto

# ─── Pruebas / demo sin claves ─────────────────────────────────────────────
test:      ## Ejecuta los tests (no necesitan BD ni claves)
	LLM_PROVIDER=fake python -m pytest

demo:      ## Demo offline del flujo completo (sin BD ni claves)
	LLM_PROVIDER=fake python -m app.demo

seed:      ## Carga datos de ejemplo en la BD (necesita 'make dev-db')
	LLM_PROVIDER=fake python -m app.seed
