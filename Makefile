.PHONY: install dev-bot dev-api test lint format typecheck

install:
	uv sync --all-extras

dev-bot:
	uv run python -m apps.bot.main

dev-api:
	uv run uvicorn apps.api.main:app --reload --port 8000

test:
	uv run pytest -v

lint:
	uv run ruff check . && uv run ruff format --check .

format:
	uv run ruff format . && uv run ruff check --fix .

typecheck:
	uv run mypy core/
