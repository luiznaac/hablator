# Docker runbook — combined image and publish

One image holds both processes: `uvicorn` (the API) and `nginx` (the built SPA, which reverse-proxies
`/api` to uvicorn and injects the API Bearer token, so the browser never holds it), supervised by
`supervisord` on separate ports. The database is not in the image; the schema is applied by
`python scripts/migrate.py` from `deploy/entrypoint.sh` before the app starts.

The app runs as `APP_ENV=prod`, so it requires an OTLP endpoint, both provider secrets and the API
Bearer token. Without them the boot fails loudly; the `mysql` service alone still starts.

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318
export MAILGUN__API_KEY=dev-hablator-mailgun-key
export NTFY__BASE_URL=http://localhost:2586
export NTFY__TOKEN=dev-hablator-ntfy-token
export AUTH__API_TOKEN=dev-hablator-api-token
docker compose up --build     # app + MySQL, full stack
#   UI   -> http://localhost:8141
#   API  -> http://localhost:8140
docker compose up -d mysql    # just the DB (host 8142), for a local backend run
```

`MAILGUN__API_URL` / `MAILGUN__FROM` / `MAILGUN__BCC` and `NTFY__BASE_URL` default to fixtures;
export them when they differ. The push topic is non-secret provider config written through
`PUT /channels/push`; the ntfy server itself is the operator's
[provisioning checklist](../ntfy-provisioning.md).

## Publish

After CI passes on a push to `master`, `.github/workflows/docker-publish.yml` (triggered on
`workflow_run` completion) builds and pushes `luiznaac/hablator:latest` and a `:v<run-number>` tag
carrying the sequential build number, to Docker Hub. It needs repo variable `DOCKERHUB_USERNAME` and
secret `DOCKERHUB_TOKEN`.
