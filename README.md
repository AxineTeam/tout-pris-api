# tout-pris-back

Backend FastAPI for Tout Pris.

## Quickstart

```bash
make build   # build the Docker image
make up      # start the API on http://localhost:8000 (docs at /docs)
make down    # stop it
```

## Development

```bash
make test    # pytest
make lint    # ruff check + format check
make fmt     # ruff autofix + format
```

A devcontainer is provided (`.devcontainer/`) based on the compose `api` service.

## Production image

The production image is built from `Dockerfile.prod` (multi-stage, [uv recommended practices](https://github.com/astral-sh/uv-docker-example)): uv builds the venv from `uv.lock` in a builder stage, and the final image contains neither uv nor pip and runs as a non-root user. This is the image published to Docker Hub on tags.

```bash
docker build -f Dockerfile.prod -t tout-pris-back .
docker run -p 8000:8000 -v tout_pris_data:/data tout-pris-back
```

The production database lives in the `/data` volume (`DATABASE_URL=sqlite:////data/tout_pris.db`), separate from the dev database (`tout_pris.db` at the repo root).

## API

- `GET /health`
- `POST /stufflists` — create a stufflist (`{"name": "..."}`)
- `GET /stufflists` — list stufflists
- `GET /stufflists/{id}` — get one
- `DELETE /stufflists/{id}` — delete one

Data is stored in SQLite (`tout_pris.db` by default, override with `DATABASE_URL`).

## OpenAPI

FastAPI generates the OpenAPI schema automatically. With the server running it is served at `/openapi.json`, with interactive docs at `/docs` (Swagger UI) and `/redoc` (ReDoc).

The schema is also committed as [`openapi.json`](openapi.json) and regenerated with `make openapi`. CI fails if the committed file drifts from the code, so regenerate it whenever routes or schemas change.

## Migrations

Schema migrations are managed with [Alembic](https://alembic.sqlalchemy.org) and run automatically when the app starts. After changing a SQLAlchemy model, generate a migration with `make migration m="describe the change"` and review the generated file; `make migrate` applies migrations without starting the server.
