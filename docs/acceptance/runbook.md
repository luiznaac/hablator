# hablator acceptance runbook

Bootstrap only: one section per service, in start order. Assertions live in the validation
manifest, never here; the acceptance browser surface launches its own Chromium, so nothing in this
file boots a browser.

## Setup context

A fresh worktree has no `backend/.venv` and no `frontend/node_modules`. Install both through the
salgadinhos sandbox (never on the host), from the repo root, before a run:

```bash
node <salgadinhos>/adapters/sandbox/run.mjs --stack python --workspace <repo> -- bash -lc 'cd backend && uv sync'
node <salgadinhos>/adapters/sandbox/run.mjs --stack node --workspace <repo> -- npm --prefix frontend ci
```

`mailgun-stub` stands in for the external Mailgun provider (the hub's only outbound third party in
this slice): it answers `200` normally, and `500` the first time a `to` field contains `fail`, so
one run produces a delivery that fails once and succeeds on retry — without leaving the machine.

The `api` service runs with `APP_ENV=test`: the same app, but a single uvicorn process (no reload)
and in-memory telemetry, so no Collector is needed. The two secrets it requires have no default in
code; the start command supplies the dev fixtures inline.

## mysql

| | |
|---|---|
| start | docker compose up -d mysql |
| ready | docker compose exec -T mysql mysqladmin ping -h 127.0.0.1 --silent |
| port  | 8142 |
| stop  | docker compose stop mysql |
| build | — |
| cwd   | <repo root> |

## mailgun-stub

| | |
|---|---|
| start | uv run python scripts/mailgun_stub.py 8199 |
| ready | http://127.0.0.1:8199/health |
| port  | 8199 |
| stop  | pkill -f "[s]cripts/mailgun_stub.py" \|\| true |
| build | — |
| cwd   | backend |

## api

| | |
|---|---|
| start | APP_ENV=test AUTH__API_TOKEN=dev-hablator-api-token MAILGUN__API_KEY=dev-hablator-mailgun-key MAILGUN__API_URL=http://127.0.0.1:8199/messages uv run poe run |
| ready | http://localhost:8140/health |
| port  | 8140 |
| stop  | pkill -f "$(pwd)/.venv" \|\| true |
| build | uv run poe migrate |
| cwd   | backend |

## web

| | |
|---|---|
| start | FRONTEND_DEV_PORT=8143 npm run dev |
| ready | http://localhost:8143/ |
| port  | 8143 |
| stop  | pkill -f "$(pwd)/node_modules/.bin/vite" \|\| true |
| build | — |
| cwd   | frontend |
