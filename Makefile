.PHONY: help build up down logs test lint fmt openapi migrate migration

.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) |  awk 'BEGIN {FS = ":.*?## "} {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

build: ## Build the Docker image
	docker compose build

up: ## Start the server (docker compose, port 8000)
	docker compose up -d

down: ## Stop the server
	docker compose down

logs: ## Follow the api container logs
	docker compose logs -f api

test: ## Run the test suite
	uv run pytest

lint: ## Check lint and formatting
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Fix lint and format the code
	uv run ruff check --fix .
	uv run ruff format .

openapi: ## Regenerate openapi.json
	uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > openapi.json

migrate: ## Apply Alembic migrations
	uv run alembic upgrade head

migration: ## Generate a migration (make migration m="description")
	uv run alembic revision --autogenerate -m "$(m)"
