setup-dev:
	uv sync --extra dev

db:
	docker compose up -d

db-stop:
	docker compose down

migrate:
	uv run python scripts/migrate.py

test:
	uv run pytest

.PHONY: setup-dev db db-stop migrate test
