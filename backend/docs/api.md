# Hablator HTTP API

The consumer document for the hub's notification API. It covers the endpoints shipped so far —
`POST /notifications`, `GET /notifications/{id}` and the channel-configuration admin surface
(`GET`/`PUT`/`DELETE /channels`) — and the error model every endpoint shares.

## Base URL and authentication

The API is served without a version prefix. In local dev uvicorn listens on `HTTP_PORT` (default
`8140`); the container publishes the API on `8140` and serves it internally on `8080`.

Every new-API request carries the single Bearer token from the environment:

```
Authorization: Bearer $AUTH__API_TOKEN
```

A missing or wrong token answers `401` with `WWW-Authenticate: Bearer`. The legacy
`POST /send-email`, `GET /health`, `GET /health/internal`, `GET /docs` and `GET /openapi.json`
stay open.

## `POST /notifications`

Creates one notification, persists one pending delivery per requested channel, attempts each
delivery synchronously, and returns the whole representation. The answer is `201` **regardless of
the delivery outcome** — read `status` (and each delivery's `status`) to learn what happened.

### Request

```json
{
  "source": "valoab",
  "content": { "subject": "Backup finished", "body": "plain text", "body_html": "<p>rich</p>" },
  "channels": [
    { "channel": "email", "recipients": ["ops@example.com"], "options": {} }
  ]
}
```

| Field | Rules |
|---|---|
| `source` | Optional, at most 64 characters. Free-form; history filters by it. |
| `content.subject` | Required, at most 998 characters. |
| `content.body` | Required, at most 256 KiB (UTF-8 bytes). Plain text. |
| `content.body_html` | Optional, at most 256 KiB. The rich alternative. The hub never renders. |
| `channels` | Required, 1–4 entries, one per channel. A duplicate channel is `400`. |
| `channels[].channel` | `email`, `push`, `sms` or `voice`. `sms`/`voice` answer `422`; `push` answers `422` until a push provider is configured (see [Channels](#channels)). |
| `channels[].recipients` | Email only, optional, 1–50 addresses. Omitted means the provider config's `recipients` default; with neither, `422`. **Rejected for push** (`422`). |
| `channels[].content` | Optional partial override merged over the base content for that delivery. `body_html: null` removes the HTML part. |
| `channels[].options` | Free-form object, adapter-validated. Email takes none in v1; any key is `422`. Push accepts `priority`, `tags` and `click` (see below). |

Unknown fields anywhere are `422 validation_error`. There is no `metadata` field. A request body
over 1 MiB is `413`; a non-JSON `Content-Type` is `415`.

`body_text` and `body_html` both present go to Mailgun as `multipart/alternative`; a single part
sends text-only or HTML-only. The new API path never derives a plain part from HTML.

### Push channel

A push delivery is one JSON publish to the ntfy server root. The **topic comes only from provider
config** (a request cannot choose one); `subject` maps to `title` and `body` to `message`.

| Rule | Value |
|---|---|
| `subject` → `title` | At most 1 KiB (UTF-8 bytes). |
| `body` → `message` | At most 4,096 bytes. |
| `options.priority` | `1`–`5` or the alias `min` / `low` / `default` / `high` / `urgent`, normalized to the integer; defaults to the provider config's `default_priority`, else `3`. |
| `options.tags` | A non-empty list of non-empty strings. |
| `options.click` | An absolute `http(s)` URL. |

A violation — an oversize title/message, an unknown option, a bad priority/tag/click, a
`recipients` entry, or a push channel with no configured provider — rejects the **whole request**
with `422 domain_error` and creates nothing. Content is never truncated or converted.

### Response — `201 Created`

`Location: /notifications/{id}` and the same DTO as `GET /notifications/{id}`:

```json
{
  "id": 42,
  "source": "valoab",
  "content": { "subject": "Backup finished", "body": "plain text", "body_html": "<p>rich</p>" },
  "status": "succeeded",
  "created_at": "2026-11-16T22:41:03.123456Z",
  "deliveries": [
    {
      "id": 77,
      "channel": "email",
      "status": "succeeded",
      "recipients": ["ops@example.com"],
      "content": { "subject": "Backup finished", "body": "plain text", "body_html": "<p>rich</p>" },
      "options": {},
      "next_attempt_at": null,
      "created_at": "2026-11-16T22:41:03.123456Z",
      "updated_at": "2026-11-16T22:41:03.123456Z",
      "attempts": [
        {
          "attempt_number": 1,
          "outcome": "succeeded",
          "provider": "mailgun",
          "provider_status": 200,
          "error_kind": null,
          "error_message": null,
          "retriable": false,
          "started_at": "2026-11-16T22:41:03.123456Z",
          "finished_at": "2026-11-16T22:41:03.123456Z"
        }
      ]
    }
  ]
}
```

- Timestamps are RFC 3339 UTC with a `Z` suffix and microsecond precision; ids are integers.
- `status` is **derived**, never stored: `succeeded` when every delivery succeeded, `failed` when
  every delivery is terminal and at least one failed, otherwise `pending`.
- `succeeded` means the provider **accepted/queued** the message, not that it reached an inbox.
- A delivery failure does not fail the request or the other channels: a Mailgun outage still
  answers `201`, with that delivery `failed` and its attempt carrying the error.
- `retriable` is the hub's classification of the failure: `true` for a timeout, a network error,
  HTTP 420/429 or any 5xx; `false` otherwise (including a 401/403 misconfiguration and an
  unexpected adapter error).

## `GET /notifications/{id}`

Returns the same representation. An unknown id is `404 resource_not_found`.

```bash
curl -sS -H "Authorization: Bearer $AUTH__API_TOKEN" \
  http://localhost:8140/notifications/42
```

## Channels

The admin surface for a channel's provider configuration. Provider **secrets stay in the
environment**; only the non-secret config is written here, and the API rejects a secret-shaped key.

### `GET /channels`

Every channel in the vocabulary — configured or not — in vocabulary order:

```json
[
  { "channel": "email", "provider": "mailgun", "configured": true,
    "config": { "from": "ops@example.com", "bcc": "archive@example.com" },
    "updated_at": "2026-11-17T09:12:44.123456Z" },
  { "channel": "push", "provider": null, "configured": false, "config": null, "updated_at": null },
  { "channel": "sms", "provider": null, "configured": false, "config": null, "updated_at": null },
  { "channel": "voice", "provider": null, "configured": false, "config": null, "updated_at": null }
]
```

`configured` is whether a config row exists. An unconfigured **email** channel still sends through
the environment's `MAILGUN__*` fallback; an unconfigured **push** channel answers `422`. No secret
value ever appears here.

### `PUT /channels/{channel}`

A full-replace upsert of `{provider, config}`: `201` when it creates the row, `200` when it
replaces one.

```bash
curl -sS -X PUT http://localhost:8140/channels/push \
  -H "Authorization: Bearer $AUTH__API_TOKEN" \
  -H "content-type: application/json" \
  -d '{"provider": "ntfy", "config": {"topic": "hablator", "default_priority": 3}}'
```

| Rule | Value |
|---|---|
| `provider` | Must be registered for the channel: `mailgun` for email, `ntfy` for push. `sms`/`voice` and an unknown channel are `422`. |
| Email `config` | `from` required; `bcc` optional; `recipients` optional (the per-delivery default, 1–50). |
| Push `config` | `topic` required; `default_priority` optional, an integer 1–5. |
| Unknown key | `422 domain_error` naming the key. |
| Secret-shaped key | `api_key`, `token`, `secret`, `password` or `auth` anywhere in a key name is `422 domain_error` naming the environment variable instead (`MAILGUN__API_KEY`, `NTFY__TOKEN`). |

A config change is logged at INFO as `config.channel.updated` with the channel and provider —
never the values.

### `DELETE /channels/{channel}`

Removes the row and answers `204`; deleting an unconfigured channel is a no-op (`204` too). After
the delete, email falls back to the environment and push answers `422` until it is configured
again.

## Error model

Errors are JSON with a stable machine-readable `code`, a human `detail`, and — for validation —
an `errors[]` list carrying the field path:

```json
{
  "code": "validation_error",
  "detail": "The request body is invalid",
  "errors": [{ "field": "channels.0.recipients", "message": "List should have at most 50 items" }]
}
```

FastAPI's default validation body never leaks.

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_argument` | A hand-checked request rule (a duplicate channel). |
| 401 | `unauthorized` | Missing or wrong Bearer; carries `WWW-Authenticate: Bearer`. |
| 404 | `resource_not_found` | Unknown notification id or unknown route. |
| 413 | `payload_too_large` | The request body exceeds 1 MiB. |
| 415 | `unsupported_media_type` | The request body is not JSON. |
| 422 | `validation_error` | Body/query shape and the generic caps; `errors[]` carries field paths. |
| 422 | `domain_error` | A channel rule: no provider for the channel, an invalid recipients shape, an unknown option. |
| 500 | `internal_error` | An unhandled error. |

## Not in this slice

History (`GET /notifications`) and manual retry (`POST /deliveries/{id}/retry`) are decided in the
spec and land in later slices. The push provider's server-side setup is the operator's
[ntfy provisioning checklist](../../docs/ntfy-provisioning.md).

The legacy `POST /send-email` request/response contract is preserved and pinned by its own golden
fixtures. The shared recipients cap (1–50) applies there too; a request it rejects keeps the
legacy `{"error": …}` 400 shape, not this envelope.
