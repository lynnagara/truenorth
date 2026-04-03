setup-dev:
	uv sync --extra dev


db:
	docker compose up -d

db-stop:
	docker compose down

migrate:
	uv run python scripts/migrate.py

trade:
	uv run truenorth trade --config config.example.yaml

test:
	uv run pytest

.PHONY: setup-dev db db-stop migrate trade test
