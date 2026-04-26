setup-dev:
	uv sync --extra dev


db:
	docker compose up -d

db-stop:
	docker compose down

migrate:
	uv run python scripts/migrate.py

trade:
	uv run truenorth trade --config config.example.yaml --cache

serve:
	uv run truenorth serve --config config.example.yaml

evaluate:
	uv run truenorth evaluate --config config.example.yaml

lint:
	uv run ruff check .
	uv run pyright

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

.PHONY: setup-dev db db-stop migrate trade serve evaluate lint format test
