# AGENTS.md — hablator monorepo

Two lanes, one repo:

- **`backend/`** — the FastAPI hexagonal service (the notification hub's API). All backend commands run from `backend/` (`cd backend && uv run poe <task>`). Its architecture, conventions and the rules for evolving it are in [backend/AGENTS.md](backend/AGENTS.md) — read that before touching `backend/`.
- **`frontend/`** — the React/Vite SPA (the debug UI). Commands run from `frontend/` (`npm --prefix frontend run <script>`). Details in [frontend/AGENTS.md](frontend/AGENTS.md).

`hablator.py` at the root is the legacy single-file email proxy. It keeps serving `POST /send-email` unchanged until the hub's compatibility adapter lands; it is not part of the container image and no new behavior goes there.

## The one cross-cutting rule

`frontend/src/api/types.ts` is a hand-maintained mirror of `backend/src/hablator/httpapi/schema.py`. Any change to a response/request DTO on one side must update the other in the same commit.

## Tooling

Root `package.json` holds script shims only (`npm run be:check`, `npm run fe:build`, `npm run check`, `npm run db`, `npm run db:migrate`, `npm run db:generate`, `npm run up`). It has no dependencies and is not a real package. `.pre-commit-config.yaml` lives at the root and scopes hooks by path (`^backend/`, `^frontend/`), and carries `no-commit-to-branch` — the git/PR conventions are enforced there, not merely stated.

Third-party install/build (`uv sync`, `npm ci`, the image build) runs in the salgadinhos sandbox, never on the host or in an agent session; the rule and the runbook are in `salgadinhos` at `global/AGENTS.md` → "Sandbox for third-party installs" and `docs/salgadinhos/sandbox-bootstrap.md`.

## Code map

- [backend/docs/code-map.md](backend/docs/code-map.md)
- [frontend/docs/code-map.md](frontend/docs/code-map.md)

## Coding standards

- [backend/CODING_STANDARDS.md](backend/CODING_STANDARDS.md)
- [frontend/CODING_STANDARDS.md](frontend/CODING_STANDARDS.md)

## Config & secrets

All backend config is env vars (`pydantic-settings`, nested keys with `__`); the reference is [backend/AGENTS.md](backend/AGENTS.md) §Configuration, and the versioned [backend/.env.example](backend/.env.example) records the env vars and their dev fixtures. Copy it to `backend/.env` (gitignored) — pydantic-settings loads that file for `cd backend && uv run poe run`. `docker compose up` reads the repo-root environment instead, for the `API_*` / `OTEL_*` values it passes through.

No real secret value is committed or defaulted in code: `API_AUTH` (the email provider secret) has no default and its absence fails the boot loudly; `MYSQL__PASSWORD` defaults to empty. The single secrets doc is `docs/salgadinhos/secrets.md` in the salgadinhos repo.

## Docker

One image (repo-root `Dockerfile`, multi-stage) ships backend + frontend together: `supervisord` runs `uvicorn` (API, `API_PORT`/8080) and `nginx` (`deploy/nginx.conf.template` — serves the built SPA on `WEB_PORT`/8081 and reverse-proxies `/api` → uvicorn). Those container-internal ports are fixed, and the image pins `MYSQL__PORT=3306` for its external database. No DB in the image. `docker-compose.yml` at the root adds MySQL for full-stack / DB-only local runs, publishing the host side on hablator's assigned block — `api` 8140, `web` 8141, `mysql` 8142 — recorded in [`.salgadinhos/ports.json`](.salgadinhos/ports.json) and listed in [README.md](README.md#ports); the Vite dev server uses `frontend-dev` 8143. The schema comes from `backend/alembic/versions/*.py`, applied by `python scripts/migrate.py` from `deploy/entrypoint.sh` before the app starts — see [backend/AGENTS.md](backend/AGENTS.md) §Database migrations. The `publish` job in `.github/workflows/ci.yml` (`needs: [backend, frontend]`, push-to-master only) pushes `luiznaac/hablator-python:latest` + `:v<run-number>` — only after a green CI run.

## Scaffold lineage

Each lane is a project instantiated from `environments` by `tools/new-project.mjs` and grafted here; the lineage pins live in `.salgadinhos/backend.yml` (`python` scaffold) and `.salgadinhos/frontend.yml` (`react` scaffold), advanced only by `template-propagate`. Don't hand-copy or hand-rename scaffold files.

## Issue tracker

Issues live as GitHub issues. The current effort is charted as a wayfinder map: [Hablator as a notification hub](https://github.com/luiznaac/hablator/issues/1).
