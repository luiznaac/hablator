#!/bin/sh
# Render the nginx site config from the template (so the ports are configurable at run time),
# migrate the database, then hand off to supervisord.
set -e

: "${API_PORT:=8080}"
: "${WEB_PORT:=8081}"
# The nginx /api/ proxy injects this token; without it the SPA would reach an API that rejects
# every call, so fail here with a clear message rather than rendering a blank Bearer.
: "${AUTH__API_TOKEN:?AUTH__API_TOKEN must be set — nginx injects it for /api/}"
export API_PORT WEB_PORT AUTH__API_TOKEN

envsubst '${WEB_PORT} ${API_PORT} ${AUTH__API_TOKEN}' \
  < /etc/nginx/templates/hablator.conf.template \
  > /etc/nginx/conf.d/hablator.conf

# Bring the schema up to date before anything can serve traffic. `set -e` above means a failed
# migration aborts the container instead of starting the app against a stale database.
echo "applying database migrations..."
python /app/scripts/migrate.py

exec supervisord -n -c /etc/supervisor/supervisord.conf
