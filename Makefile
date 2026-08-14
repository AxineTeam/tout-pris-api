.PHONY: build up down logs install test lint fmt

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .
