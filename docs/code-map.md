# Code map

Module → the files that matter → the seam a change crosses, plus the app entry points. Hand-authored:
re-author it with the `code-map` skill when the code moves. This map indexes the repo and owns the
cross-lane seam; each lane's own map carries its module detail.

## Modules

### `backend/` — the notification hub service
**Purpose**: the FastAPI hexagonal service that owns the notification, delivery and attempt domain, the email and push providers, and the legacy `POST /send-email` adapter.
**Files**: `backend/src/hablator/`; `backend/tests/`; `backend/alembic/versions/`; detail in the [backend code map](../backend/docs/code-map.md)
**Seam(s)**:
- **Lane map** — [backend/docs/code-map.md](../backend/docs/code-map.md) is the module index for the five layers (`usecase`, `persistence`, `gateway`, `httpapi`, `application`), their ports and the schema history.
- **Edge DTO seam** — `backend/src/hablator/httpapi/schema.py` is the HTTP shape; `frontend/src/api/types.ts` mirrors it by hand, so a DTO change updates both in one commit.
- **Contract** — the endpoints and their rules are documented in [backend/docs/api.md](../backend/docs/api.md); the legacy adapter `backend/src/hablator/httpapi/controller/legacy_email_controller.py` is pinned byte-for-byte by `backend/tests/integration/test_legacy_send_email.py`.

### `frontend/` — the debug SPA
**Purpose**: the React/Vite console that sends a notification, reads the delivery history and shows health and channel configuration.
**Files**: `frontend/src/`; detail in the [frontend code map](../frontend/docs/code-map.md)
**Seam(s)**:
- **Lane map** — [frontend/docs/code-map.md](../frontend/docs/code-map.md) is the module index for the wire layer, the route screens, the presentational atoms, the pure helpers and the toolchain.
- **Wire seam** — `frontend/src/api/types.ts` (the DTO mirror) and `frontend/src/api/client.ts` (the one `api` object); a component never calls `fetch`, and a new call is a typed function there, a hook in `queries.ts`, then a panel.

### `deploy/` — the container entry
**Purpose**: render the nginx site config, apply the schema, then run both processes under `supervisord`.
**Files**: `deploy/entrypoint.sh`; `deploy/nginx.conf.template`; `deploy/supervisord.conf`
**Seam(s)**:
- `entrypoint.sh` fails loudly without `AUTH__API_TOKEN`, `envsubst`s only `${WEB_PORT}`, `${API_PORT}` and `${AUTH__API_TOKEN}`, runs `scripts/migrate.py`, then `exec`s `supervisord` — a failed migration aborts the container instead of serving against a stale schema.
- `nginx.conf.template` serves the built SPA and reverse-proxies `/api/` to uvicorn with the Bearer token injected, so the browser never holds it; `frontend/vite.config.ts`'s dev proxy mirrors that injection.
- `supervisord.conf` runs uvicorn and nginx; the API's `stopwaitsecs` lets the telemetry SDK flush on shutdown.

### Repo root — one image, one toolchain, one CI
**Purpose**: the script shims, the multi-stage image, the compose stack, the pre-commit hooks and the two workflows.
**Files**: `package.json`; `Dockerfile`; `docker-compose.yml`; `.pre-commit-config.yaml`; `scripts/release.sh`; `.github/workflows/ci.yml`; `.github/workflows/docker-publish.yml`; `.github/release.yml`; `CHANGELOG.md`; `.salgadinhos/ports.json`
**Seam(s)**:
- `package.json` is a shim only: `npm run check` mirrors pre-commit (backend `poe check` + frontend `check` + build), and `npm run db` / `npm run db:migrate` wrap compose and Alembic. The real toolchains are `uv` in `backend/` and `npm` in `frontend/`.
- `Dockerfile` builds the single image (backend + built SPA); `docker-compose.yml` adds MySQL and publishes the assigned port block recorded in `.salgadinhos/ports.json`.
- `ci.yml` runs the two lanes as independent jobs; `docker-publish.yml` builds the image with `push: false` on pull requests and publishes only on a `v*` release tag (cut by `scripts/release.sh`), so a merge to `master` never publishes.

### `docs/` — the doc set
**Purpose**: the reserved documentation layout and the flat topical docs.
**Files**: `docs/code-map.md`; `docs/adr/`; `docs/runbooks/`; `docs/assets/`; `docs/deploy-cutover.md`; `docs/ntfy-provisioning.md`
**Seam(s)**: the layout is fixed by the family documentation standard — `code-map.md`, `adr/`, `assets/`, `runbooks/`, `research/` are the only reserved paths and every other doc is flat. The README's `## Docs` is the single index; this map is linked from the root `AGENTS.md`.

## Entry points

- `deploy/entrypoint.sh` — the container start: render nginx, migrate, hand off to `supervisord`.
- `backend/src/hablator/application/boot.py` — the API process: `app` is what uvicorn imports and `main()` runs uvicorn on `HTTP_PORT`, both building the `Container`.
- `frontend/index.html` → `frontend/src/main.tsx` → `frontend/src/App.tsx` — the SPA: mount React with the query client and the router, whose index route is `Console`.
- `docker-compose.yml` — the full-stack local entry: the app image plus its MySQL sidecar.
- `scripts/release.sh` — cut a release: validate the repository state, then create the `v*` tag and GitHub Release.
- `package.json` scripts — the local dev entry: `npm run be:run` and `npm run fe:dev`.
