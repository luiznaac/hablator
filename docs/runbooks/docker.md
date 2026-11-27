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

A merge to `master` never publishes. `.github/workflows/docker-publish.yml` publishes
`luiznaac/hablator` only on a deliberate `v*` release tag, pushed by `scripts/release.sh <version>`:
it tags immutable semver, major.minor and short-SHA images, moving `latest` only on a release. On a
pull request it builds the same image with `push: false`, so a broken Dockerfile fails CI before a
release discovers it. Publishing needs repo variable `DOCKERHUB_USERNAME` and secret
`DOCKERHUB_TOKEN`.
