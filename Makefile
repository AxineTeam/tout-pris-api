.PHONY: build up down logs test lint fmt openapi

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

openapi:
	uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > openapi.json
