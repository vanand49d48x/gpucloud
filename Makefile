.PHONY: run.api run.web db.up db.down

ENV_FILE ?= .env

db.up:
	docker-compose up -d postgres redis

db.down:
	docker-compose down

db.migrate:
	cd apps/api && alembic revision --autogenerate -m "$(m)"

db.upgrade:
	cd apps/api && alembic upgrade head

run.api:
	cd apps/api && python -m pip install -U pip && python -m pip install -e .
	uvicorn apps.api.app.main:app --reload --port 8080

run.worker:
	cd apps/api && python -m apps.api.workers

run.web:
	cd apps/web && npm run dev
