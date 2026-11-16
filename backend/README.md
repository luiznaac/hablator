# backend

The FastAPI hexagonal service — the notification hub's API. Same layered shape as the family's `python` scaffold: a hand-written composition root (no DI framework), SQLAlchemy 2 async / MySQL, httpx, Ruff, mypy `--strict`, import-linter for the layer rules, and a Testcontainers integration harness. Today it ships one working vertical slice — a health check — plus the settings the email channel will read.

## Quick start

```bash
uv sync                       # create .venv + install everything
docker compose up -d mysql    # from the repo root: MySQL on host 8142
uv run poe migrate            # apply Alembic migrations
uv run poe run                # http://localhost:8140/health
```

## Tasks (`uv run poe <task>`)

| task                | what it does                                            |
|---------------------|--------------------------------------------------------|
| `run`               | module entrypoint on `HTTP_PORT` (reload in `dev`)      |
| `lint` / `format`   | Ruff                                                    |
| `typecheck`         | mypy `--strict`                                         |
| `contracts`         | import-linter (layer rules)                             |
| `test`              | all tests                                               |
| `test-unit`         | unit tests only (no Docker)                             |
| `test-integration`  | integration tests (needs a Docker daemon)               |
| `migrate`           | apply pending Alembic migrations                        |
| `migrate:generate`  | autogenerate one from `Base.metadata`                   |
| `check`             | the Docker-free fast gate (lint, format, types, contracts, unit) |

See [AGENTS.md](AGENTS.md) for the architecture, the configuration table and the rules for evolving it. The lane's deploy bits (image, compose, CI) live at the repo root.
