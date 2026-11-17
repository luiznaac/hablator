# Deploy cutover — hablator to the combined image

The hablator repo now ships the hub behind the legacy `POST /send-email` adapter; the old
single-file `hablator.py` proxy is gone. This note is the hand-off for the **iac** repo, which is
not a declared sibling of this repo (no `.salgadinhos/` lane sentinel), so the stack change lands
there as its own PR.

Reference stack: `iac/homelab/stacks/hablator/` (`stack.yml`, `compose.yaml.j2`, `.env.example`)
and the image pin `stacks_hablator_image` in `iac/roles/stacks/defaults/main.yml`.

## What the image now is

One image, two processes under `supervisord`:

| Process | Container port | Env key |
| --- | --- | --- |
| `uvicorn` (API: `/send-email`, `/health`, future `/notifications`) | `8080` | `API_PORT` / `HTTP_PORT` |
| `nginx` (SPA on `/`, proxies `/api/` → `8080`) | `8081` | `WEB_PORT` |

The image ships its own `HEALTHCHECK` (`curl` on `/health/internal` and the web root), runs
`python scripts/migrate.py` from `deploy/entrypoint.sh` before serving, and requires the database
schema to be reachable at boot. The database is **not** in the image.

## Changes for `iac/homelab/stacks/hablator/`

1. **Image pin** — `stacks_hablator_image` becomes `luiznaac/hablator-python:latest@<digest>`
   (pin the digest of the first green `Docker publish` run, as the other stacks do).
2. **Ports** — the legacy consumers hit `host:6903/send-email`, so publish the API:
   `"${HABLATOR_PORT:-6903}:8080"`. The web UI is a second, optional publish
   (`"${HABLATOR_WEB_PORT:-6904}:8081"`); only `6903` is required for the legacy contract.
   The old `:80` mapping is gone.
3. **Environment** — set `MAILGUN__API_KEY` / `MAILGUN__API_URL` / `MAILGUN__FROM` / `MAILGUN__BCC`
   (the email channel's env keys and the legacy adapter's fallback), and add:
   - `APP_ENV=prod`, `LOG_LEVEL=INFO`
   - `HTTP_PORT=8080`, `API_PORT=8080`, `WEB_PORT=8081`
   - `MYSQL__HOST`, `MYSQL__PORT=3306`, `MYSQL__USER`, `MYSQL__PASSWORD`, `MYSQL__DATABASE=hablator`
     (point at the shared MySQL the other stacks use)
   - `OTEL_SERVICE_NAME=hablator`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`,
     `OTEL_SEMCONV_STABILITY_OPT_IN=http,database`
   - `AUTH__API_TOKEN` — the new API's Bearer token, required now that `POST /notifications`
     and `GET /notifications/{id}` ship.
   - `NTFY__BASE_URL` / `NTFY__TOKEN` — the push channel's server root and `hablator-backend`
     admin token (a secret, no default). Provision ntfy per
     [ntfy-provisioning.md](ntfy-provisioning.md), then write the topic once through
     `PUT /channels/push` (non-secret provider config).
4. **Database** — create the `hablator` database with `utf8mb4` / `utf8mb4_0900_ai_ci` and
   register it in `restic_mysql_databases` (the migration creates the tables; the database itself
   is iac's).
5. **Healthcheck** — the stack comment "luiznaac/hablator ships none" is now false: the image
   ships one. Rely on it (or copy the same `curl` probe into the compose file if the renderer
   strips `HEALTHCHECK`), and drop the comment.
6. **Memory cap** — the control-plane table's `64M` is too small for Python + nginx + supervisord;
   raise it (e.g. `256M`) and record the new value in the table.
7. **`stack.yml`** — `store: none` becomes a store-backed stack (MySQL), and the comment "the
   stateless mailer" no longer holds.

## Verification after the cutover

- `curl -fsS http://<host>:6903/health/internal` → `{"is_healthy": true}`.
- `curl -fsS -X POST http://<host>:6903/send-email -H 'content-type: application/json' \
  -d '{"emails":["you@example.com"],"subject":"cutover","text":"<p>ok</p>"}'` → the legacy
  `200 {"message": "Emails sent successfully", "response": ...}` body.
- The stack's health status is `healthy` (the image probe), and the OTLP collector receives
  `hablator` logs/metrics.
