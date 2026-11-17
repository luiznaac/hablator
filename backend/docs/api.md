# Hablator HTTP API

The consumer document for the hub's notification API. It covers `POST /notifications`,
`GET /notifications`, `GET /notifications/{id}` and `POST /deliveries/{id}/retry`, plus the error
model every endpoint shares.

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
| `channels[].channel` | `email`, `push`, `sms` or `voice`. `sms`/`voice` (and, in this slice, `push`) answer `422` until a provider is configured. |
| `channels[].recipients` | Email only, optional, 1–50 addresses. Omitted means the provider config's `recipients` default; with neither, `422`. |
| `channels[].content` | Optional partial override merged over the base content for that delivery. `body_html: null` removes the HTML part. |
| `channels[].options` | Free-form object, adapter-validated. Email takes none in v1; any key is `422`. |

Unknown fields anywhere are `422 validation_error`. There is no `metadata` field. A request body
over 1 MiB is `413`; a non-JSON `Content-Type` is `415`.

`body_text` and `body_html` both present go to Mailgun as `multipart/alternative`; a single part
sends text-only or HTML-only. The new API path never derives a plain part from HTML.

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

## `GET /notifications`

The notification history, newest first (`created_at DESC, id DESC`), with offset pagination and
filters. Every filter is optional and combines with the others.

| Query | Rules |
|---|---|
| `source` | Exact match on the notification's `source`. |
| `channel` | `email`, `push`, `sms` or `voice`. Matches a notification with at least one delivery on that channel (a delivery-level `EXISTS`). |
| `status` | The **derived** notification status: `pending`, `succeeded` or `failed`. |
| `created_after` | Inclusive lower bound on `created_at`, RFC 3339. |
| `created_before` | Exclusive upper bound on `created_at`, RFC 3339. |
| `limit` | Page size, 1–100, default 20. |
| `offset` | Rows to skip, `>= 0`, default 0. |

A bound violation or an unknown `channel`/`status` is `422 validation_error` with the offending
field in `errors[]`.

### Response — `200 OK`

```json
{
  "items": [
    {
      "id": 42,
      "source": "valoab",
      "subject": "Backup finished",
      "status": "succeeded",
      "created_at": "2026-11-16T22:41:03.123456Z",
      "channels": ["email", "push"]
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

- `total` is the count **after filtering**, so a pager can render page numbers.
- `subject` is the notification's base subject; each delivery may carry an override.
- `channels` lists the channels the notification was sent through, in delivery order.
- An empty result is `{"items": [], "total": 0, "limit": <limit>, "offset": <offset>}`.

```bash
curl -sS -H "Authorization: Bearer $AUTH__API_TOKEN" \
  "http://localhost:8140/notifications?status=failed&channel=push&limit=50"
```

## `GET /notifications/{id}`

Returns the same representation. An unknown id is `404 resource_not_found`.

```bash
curl -sS -H "Authorization: Bearer $AUTH__API_TOKEN" \
  http://localhost:8140/notifications/42
```

## `POST /deliveries/{id}/retry`

Retries one delivery synchronously against its provider and returns the delivery representation
after the attempt.

- Allowed on a `failed` or `pending` delivery. A failed delivery reopens as pending, is attempted
  again, and its new Attempt carries the next `attempt_number` (append-only history).
- `409 conflict` when the delivery is `in_progress` or already `succeeded` — the hub refuses to
  double-send.
- `404 resource_not_found` for an unknown delivery id.
- There is **no idempotency key**: a double-click can double-send. The UI disables the button in
  flight; an API consumer must do the same.

```json
{
  "id": 77,
  "channel": "email",
  "status": "succeeded",
  "recipients": ["ops@example.com"],
  "content": { "subject": "Backup finished", "body": "plain text", "body_html": null },
  "options": {},
  "next_attempt_at": null,
  "created_at": "2026-11-16T22:41:03.123456Z",
  "updated_at": "2026-11-16T22:43:10.000000Z",
  "attempts": [
    { "attempt_number": 1, "outcome": "failed", "provider": "mailgun", "provider_status": 503, "...": "..." },
    { "attempt_number": 2, "outcome": "succeeded", "provider": "mailgun", "provider_status": 200, "...": "..." }
  ]
}
```

`attempts` is the full append-only history, oldest first; the retry adds exactly one entry. A
retry does not touch the notification's other deliveries, and the notification's derived status
follows from all of them.

```bash
curl -sS -X POST -H "Authorization: Bearer $AUTH__API_TOKEN" \
  http://localhost:8140/deliveries/77/retry
```

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
| 404 | `resource_not_found` | Unknown notification/delivery id or unknown route. |
| 409 | `conflict` | A retry of an `in_progress` or `succeeded` delivery. |
| 413 | `payload_too_large` | The request body exceeds 1 MiB. |
| 415 | `unsupported_media_type` | The request body is not JSON. |
| 422 | `validation_error` | Body/query shape and the generic caps; `errors[]` carries field paths. |
| 422 | `domain_error` | A channel rule: no provider for the channel, an invalid recipients shape, an unknown option. |
| 500 | `internal_error` | An unhandled error. |

## Not in this slice

Channel configuration (`GET`/`PUT`/`DELETE /channels`) is decided in the spec and lands in a later
slice.

The legacy `POST /send-email` request/response contract is preserved and pinned by its own golden
fixtures. The shared recipients cap (1–50) applies there too; a request it rejects keeps the
legacy `{"error": …}` 400 shape, not this envelope.
