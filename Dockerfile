# Dev image: full uv toolchain + dev dependencies, source mounted from the host,
# Django runserver with its auto-reloader. See Dockerfile.prod for the shipped image.
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

WORKDIR /app

# UV_COMPILE_BYTECODE: precompile .pyc at install time for faster startup.
# UV_LINK_MODE=copy: avoid hardlink warnings when cache and venv are on different filesystems.
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Layer 1 — dependencies only (--no-install-project), rebuilt only when the lock changes.
# cache mount: persistent uv download cache, never baked into the image.
# bind mounts: expose the lock files without COPYing them into a layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Layer 2 — install the project itself on top; rebuilt on every source change,
# but reuses the cached dependency layer above.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Put the venv on PATH so bare `python`/`django-admin` resolve to it.
ENV PATH="/app/.venv/bin:$PATH"

# Outside /app so the compose bind mount of the sources cannot shadow it.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
