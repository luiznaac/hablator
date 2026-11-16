# syntax=docker/dockerfile:1

# ===========================================================================
# One image, two services:
#   - uvicorn  (the FastAPI backend)          -> ${API_PORT}, default 8080
#   - nginx    (the built SPA + /api proxy)   -> ${WEB_PORT}, default 8081
# supervised together by supervisord. These container-internal ports are fixed;
# the host publish side lives in docker-compose.yml. HTTP_PORT pins the app's
# configured port to the same 8080 so the self-health URL is derived correctly,
# and MYSQL__PORT pins the external database to 3306. An explicit env value still
# overrides either.
#
# The database is NOT part of this image. Point MYSQL__* at an external MySQL
# (docker-compose.yml has one for local/full-stack runs).
# ===========================================================================

# ---------------------------------------------------------------------------
# Stage 1 — build the frontend SPA to static files
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /fe

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Served at the nginx root; the API is reached through nginx's /api proxy
# (see deploy/nginx.conf.template), so the client's base stays "/api".
ENV VITE_BASE=/ \
    VITE_API_BASE=/api
RUN npm run build          # -> /fe/dist

# ---------------------------------------------------------------------------
# Stage 2 — resolve backend dependencies into /app/.venv
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 3 — runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor gettext-base curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    API_PORT=8080 \
    WEB_PORT=8081 \
    HTTP_PORT=8080 \
    MYSQL__PORT=3306

COPY --from=backend --chown=app:app /app /app
COPY --from=frontend /fe/dist /var/www/hablator
COPY deploy/nginx.conf.template /etc/nginx/templates/hablator.conf.template
COPY deploy/supervisord.conf /etc/supervisor/conf.d/hablator.conf
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8080 8081

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${WEB_PORT}/" >/dev/null \
        && curl -fsS "http://localhost:${API_PORT}/health/internal" >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
