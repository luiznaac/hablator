# hablator

Notification hub for the homelab: it takes send requests from other projects and delivers them through channels, recording the history of every delivery attempt.

| Path         | What                                                                        |
| ------------ | --------------------------------------------------------------------------- |
| [`backend/`](backend/)   | FastAPI + hexagonal service (uv, SQLAlchemy/MySQL, Alembic). See [backend/README.md](backend/README.md) and [backend/AGENTS.md](backend/AGENTS.md). |
| [`frontend/`](frontend/) | React + Vite SPA — the debug UI. See [frontend/AGENTS.md](frontend/AGENTS.md). |

The domain glossary is [`CONTEXT.md`](CONTEXT.md). The frontend's `src/api/types.ts` mirrors the backend's `httpapi/schema.py`; keep them in sync in the same change — that's the reason these two live in one repo.

The legacy `POST /send-email` contract is served by the backend's compatibility adapter over the hub's email channel. Golden fixtures pin its responses byte-for-byte, so existing consumers (valoab via chameidor) need no change; the old single-file `hablator.py` proxy is gone.

## Dev

```bash
npm run setup      # npm install in frontend/ + uv sync in backend/
npm run db         # start MySQL (docker) for the backend
npm run db:migrate # apply Alembic migrations
```

Then, in two shells:

```bash
npm run be:run     # backend  -> http://localhost:8140
npm run fe:dev     # frontend -> http://localhost:8143  (proxies /api -> :8140)
```

## Ports

Local host ports are hablator's assigned block, recorded in [`.salgadinhos/ports.json`](.salgadinhos/ports.json). Only the published side of a compose mapping varies — container-internal ports stay fixed.

| Role | Host port | Env key | Container-internal |
| --- | --- | --- | --- |
| `api` | `8140` | `HTTP_PORT` | `8080` (`API_PORT`) |
| `web` (combined image: SPA + `/api` proxy) | `8141` | `WEB_HOST_PORT` | `8081` (`WEB_PORT`) |
| `mysql` | `8142` | `MYSQL__PORT` | `3306` |
| `frontend-dev` (Vite) | `8143` | `FRONTEND_DEV_PORT` | — |

A gitignored `.env` may override a host port locally; the committed defaults above apply to a fresh clone. The block is dev-only: the published image keeps the canonical `8080`/`3306` unless a port is set explicitly. The DB port recipe is `docker compose port mysql 3306`.

## Docker

One image holds both processes — `uvicorn` (API) and `nginx` (the built SPA, which also reverse-proxies `/api` to uvicorn) — supervised by `supervisord`, on separate ports. The database is **not** in the image; the schema is applied by `python scripts/migrate.py` from `deploy/entrypoint.sh` before the app starts.

The app runs as `APP_ENV=prod`, so it requires an OTLP endpoint, the email provider key and the API Bearer token. Export `OTEL_EXPORTER_OTLP_ENDPOINT` (for a Collector on the host, `http://host.docker.internal:4318`), `MAILGUN__API_KEY` (plus `MAILGUN__API_URL` / `MAILGUN__FROM` / `MAILGUN__BCC` when they differ from the fixtures) and `AUTH__API_TOKEN`. Without them the app's boot fails loudly; the `mysql` service alone still starts.

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318
export MAILGUN__API_KEY=dev-hablator-mailgun-key
export AUTH__API_TOKEN=dev-hablator-api-token
docker compose up --build     # app + MySQL, full stack
#   UI   -> http://localhost:8141
#   API  -> http://localhost:8140
docker compose up -d mysql    # just the DB (host :8142), for local `cd backend && uv run poe run`
```

**Publishing:** after CI passes on a push to `master`, the `publish` job in `.github/workflows/ci.yml` builds and pushes `luiznaac/hablator-python:latest` and `:v<run-number>` (a sequential build number) to Docker Hub. Needs repo secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`.

## Checks

```bash
npm run check      # backend `poe check` + frontend `npm run check` + frontend build
```

CI (`.github/workflows/ci.yml`) runs the backend (full `poe test`, integration suite included) and frontend jobs independently, then a `publish` job (master pushes only) that gates the Docker image on both.

`package.json` at the repo root is only a script shim (no dependencies) — the real toolchains are `uv` in `backend/` and `npm` in `frontend/`.
