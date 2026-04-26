.PHONY: infra-up redis-up infra-down db-migrate db-current db-history api-dev worker web-dev

infra-up:
	docker compose up -d

redis-up:
	docker compose up -d redis

infra-down:
	docker compose down

db-migrate:
	cd api && uv run alembic upgrade head

db-current:
	cd api && uv run alembic current

db-history:
	cd api && uv run alembic history

api-dev:
	cd api && uv run uvicorn app.main:app --reload

worker:
	cd api && uv run celery -A app.workers.celery_app:celery_app worker --loglevel=info

web-dev:
	cd web && pnpm dev
