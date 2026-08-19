# tout-pris-back

Backend Django for Tout Pris, with [Django REST Framework](https://www.django-rest-framework.org) for the API, [drf-spectacular](https://drf-spectacular.readthedocs.io) for its OpenAPI schema, and [drf-pydantic](https://github.com/georgebv/drf-pydantic) to derive serializers from Pydantic models.

There is no Makefile: `manage.py` is the entry point for everything that touches the application or the database, and this README lists every other command.

## Quickstart

```bash
docker compose build   # build the dev image
docker compose up -d   # start the API on http://localhost:8000 (docs at /api/docs)
docker compose down    # stop it
```

Migrations are applied by the container entrypoint on every start, so the database is always up to date.

## Commands

Without Docker, everything runs through uv (`uv sync` once to install the dependencies). Inside Docker, prefix the same commands with `docker compose exec api`.

### Docker

```bash
docker compose build              # build the dev image
docker compose up -d              # start the API in the background
docker compose down               # stop it
docker compose logs -f api        # follow the API logs
docker compose exec api sh        # open a shell in the running container
```

### Server

```bash
uv run python manage.py runserver 0.0.0.0:8000        # dev server with auto-reload
uv run python manage.py runserver_plus 0.0.0.0:8000   # same with the Werkzeug debugger (django-extensions)
```

### Database and migrations

```bash
uv run python manage.py migrate                    # apply the migrations
uv run python manage.py makemigrations             # generate the migrations for the model changes
uv run python manage.py showmigrations             # list the migrations and their state
uv run python manage.py sqlmigrate accounts 0001   # print the SQL of a migration without applying it
uv run python manage.py reset_db                   # drop the dev database (django-extensions)
uv run python manage.py createsuperuser            # create an admin account
```

The dev database is a SQLite file (`tout_pris.db`) never versioned in git; rebuild it with `reset_db` then `migrate`.

### Shell and checks

```bash
uv run python manage.py shell_plus   # shell with every model imported (django-extensions)
uv run python manage.py check        # run the Django system checks
```

### Tests, lint and format

```bash
uv run pytest                # run the test suite (fails under 100% coverage)
uv run ruff check .          # lint
uv run ruff check --fix .    # lint and autofix
uv run ruff format .         # format
uv run ruff format --check . # check the formatting without rewriting
npx markdownlint-cli2 "**/*.md"   # lint the markdown, as CI does
```

Generated migrations are written with Django's own formatting: run `uv run ruff format .` after `makemigrations`.

### OpenAPI export

```bash
uv run python manage.py spectacular --file openapi.yaml
```

### Production

```bash
DJANGO_SECRET_KEY=... docker compose -f docker-compose.prod.yml up -d
```

## API

- `GET /api/health` — health check
- `GET /api/docs/` — interactive documentation rendered by drf-spectacular
- `GET /api/schema/` — OpenAPI schema served by the running app
- `/admin/` — Django admin

## OpenAPI

drf-spectacular generates the schema from the code. It is committed as [`openapi.yaml`](openapi.yaml) and regenerated with the `spectacular` command above. CI fails if the committed file drifts from the code, so regenerate it whenever routes or schemas change.

## Migrations

Schema migrations are Django migrations, applied by the Docker entrypoint at container start — never by the application code. After changing a model, generate a migration with `makemigrations`, read the generated file, and check the SQL with `sqlmigrate` when in doubt. CI fails if a model change has no migration.

## Configuration

Settings are read from the environment.

| Variable | Default | Role |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///tout_pris.db` | Database, parsed by dj-database-url. |
| `DJANGO_SECRET_KEY` | an insecure development key | Django secret key. Mandatory in production. |
| `DJANGO_DEBUG` | `true` | Debug mode. Set it to `false` in production. |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hosts. |
| `BREVO_API_KEY` | empty | Brevo API key. When empty, `send_email` logs the subject and the recipient, and sends nothing: that is the dev and test mode, no network call is ever made. |
| `MAIL_FROM_EMAIL` | `no-reply@tout-pris.app` | Sender address, must be a sender validated in Brevo. |
| `MAIL_FROM_NAME` | `Tout Pris` | Sender display name. |

The Brevo key and the secret key are secrets: never commit them, pass them through the environment.

## Transactional emails

Transactional emails (invitations, email verification, password reset) are sent through [Brevo](https://developers.brevo.com) with the synchronous `brevo-python` client, from `tout_pris/mail.py`.

## Production image

The production image is built from `Dockerfile.prod` (multi-stage, [uv recommended practices](https://github.com/astral-sh/uv-docker-example)): uv builds the venv from `uv.lock` in a builder stage, and the final image contains neither uv nor pip, runs as a non-root user, and serves the WSGI application with gunicorn.

CI publishes it to Docker Hub for `linux/amd64` and `linux/arm64` (Raspberry Pi and other ARMv8 boards): every merge on `main` pushes the `dev` tag, and every git tag pushes the matching semver tags plus `latest`.

The production settings live in `docker-compose.prod.yml`: the database is stored in the `tout_pris_data` named volume mounted on `/data` (`DATABASE_URL=sqlite:////data/tout_pris.db`), separate from the dev database (`tout_pris.db` at the repo root).

## Project layout

- `manage.py` — Django entry point
- `tout_pris/` — project package: `settings.py`, `urls.py` (admin, and the API mounted on `/api/`), `views.py`, `mail.py`, `wsgi.py`, `asgi.py`
- `accounts/` — the custom `User` model, referenced by `AUTH_USER_MODEL` since the initial migration
- `tests/` — pytest-django test suite
- `docs/api/` — the API conventions: status codes, household scoping, schemas, collections
- `docs/model/` — the functional need behind the data model, independent of the framework

A devcontainer is provided (`.devcontainer/`) based on the compose `api` service.
