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
