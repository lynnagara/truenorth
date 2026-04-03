setup-dev:
	uv sync --extra dev

test:
	uv run pytest

.PHONY: setup-dev test
