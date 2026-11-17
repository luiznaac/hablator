# ntfy provisioning checklist

The operator checklist for the push channel's self-hosted ntfy instance. The hub publishes JSON to
the server root with one admin Bearer token; the topic is non-secret provider config written
through the admin API, and the instance stays deny-all behind TLS.

The stack change itself (the ntfy container, its volume, its TLS termination) belongs to the iac
repo, like the rest of the hablator deploy ([deploy-cutover.md](deploy-cutover.md)).

## 1. Server config (`server.yml`)

```yaml
base-url: "https://ntfy.example.com"
cache-file: "/var/cache/ntfy/cache.db"
auth-file: "/var/lib/ntfy/user.db"
auth-default-access: "deny-all"
upstream-base-url: "https://ntfy.sh"
behind-proxy: true
```

- **`cache-file`** keeps messages across a restart and serves the iOS app's metadata poll.
- **`auth-file`** holds the users and their access tokens.
- **`auth-default-access: deny-all`** is the security posture: no anonymous publish or subscribe.
- **`upstream-base-url: https://ntfy.sh`** is required for the iOS app (see the relay caveat
  below). It must not change the content path — content stays on this instance.
- **TLS** — terminate HTTPS in front of ntfy (the reverse proxy) and expose only `443`; the app's
  `NTFY__BASE_URL` is the `https://` base URL.

## 2. Admin user and token

```bash
docker exec -it ntfy ntfy user add --role=admin hablator-backend
docker exec -it ntfy ntfy token add --label=hablator hablator-backend
```

The token (`tk_…`) is a secret: it goes in the hub's `NTFY__TOKEN` environment, never in the
database, a config file or a log line. The hub's admin API rejects any secret-shaped key
(`api_key|token|secret|password|auth`) for exactly this reason.

Grant the user read-write access on the topic the hub will publish to (an admin user already
has it; a dedicated publisher would need `ntfy access <user> <topic> rw`).

## 3. iOS subscription

Subscribe in the ntfy iOS app to the `https://` base URL and the topic, authenticating as
`hablator-backend` (the app accepts the username/password, or an access token). The subscription
needs `read` access on the topic; with `deny-all`, an unauthenticated subscription is rejected.

## 4. Relay caveat

Apple only delivers push to an app through APNs, so the self-hosted ntfy reaches the iPhone by
asking `ntfy.sh` to send a **metadata-only** poll request. The message content never leaves this
instance: `ntfy.sh` sees the topic and a "fetch your messages" signal, and the app then downloads
the content directly from `https://ntfy.example.com`. That is the accepted trade-off for avoiding a
native APNs companion app; `upstream-base-url` is what enables it.

## 5. Hub environment and provider config

```bash
NTFY__BASE_URL=https://ntfy.example.com
NTFY__TOKEN=tk_…            # the hablator-backend admin token, no default in code
```

The topic and the default priority are non-secret provider config, written once through the admin
API (no restart, no SQL):

```bash
curl -sS -X PUT "$HUB/channels/push" \
  -H "Authorization: Bearer $AUTH__API_TOKEN" \
  -H "content-type: application/json" \
  -d '{"provider":"ntfy","config":{"topic":"hablator","default_priority":3}}'
```

`topic` is required; `default_priority` is an optional integer 1–5. A request cannot choose a
topic, and `recipients` is rejected for push. `DELETE /channels/push` removes the row, after which
the channel answers `422` until it is configured again.

## 6. Verification

1. **Deny-all holds** — an anonymous publish is refused:

   ```bash
   curl -sS -o /dev/null -w '%{http_code}\n' -d "nope" https://ntfy.example.com/hablator
   # expect 403
   ```

2. **The hub's provider is configured** — `GET /channels` shows push `configured: true` with the
   `ntfy` provider and no secret values.

3. **End to end** — send a push through the hub:

   ```bash
   curl -sS -X POST "$HUB/notifications" \
     -H "Authorization: Bearer $AUTH__API_TOKEN" \
     -H "content-type: application/json" \
     -d '{"content":{"subject":"Push check","body":"it works"},"channels":[{"channel":"push"}]}'
   ```

   Expect `201`, the push delivery `succeeded`, its attempt's `provider_status: 200`, and the
   notification to arrive on the subscribed phone.
