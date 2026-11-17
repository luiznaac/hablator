# Code map

Module → key files → seam index, plus the app entry points. Hand-authored: re-author it with the
`code-map` skill when the code moves.

The layers are one package, `src/hablator/`, with one sub-package each; `import-linter` enforces
that dependencies point inward (`application → httpapi/persistence/gateway → usecase`). Inside
`usecase` the slice DAG is `delivery → notification → channel`, enforced by
`tests/unit/test_architecture.py`.

## Modules

### `usecase/` — domain models, ports and services
**Purpose**: the pure core. Owns the notification aggregate, the channel ports and rules, the
delivery dispatcher, the health slice and the cross-cutting helpers. Imports no framework —
`import-linter` forbids `fastapi`, `sqlalchemy`, `httpx`, `uvicorn` and `pydantic` here.
**Files**: `usecase/notification/{model,ports,service}.py`; `usecase/delivery/{ports,dispatcher}.py`;
`usecase/channel/{model,ports,classify,defaults,registry,telemetry}.py`;
`usecase/health/{checker,gateway,telemetry}.py`; `usecase/configuration/transaction.py`;
`usecase/commons/{time,logging,request_context,asyncx,exceptions}.py`
**Seam(s)**:
- **`NotificationService`** (`notification/service.py`) — `send(request)` validates every channel
  rule inside the create transaction (duplicate channel, no registered provider, the adapter's
  own `prepare`), persists the notification + one pending delivery per channel, then fans out;
  `read(id)` returns the detail or raises `ResourceNotFoundError`; `history(query)` returns one
  filtered page; `retry(delivery_id)` reopens a `failed`/`pending` delivery (or refuses an
  `in_progress`/`succeeded` one with `DeliveryNotRetriableError`) and dispatches it synchronously.
  Depends on `INotificationRepository`, `IDeliveryDispatcher`, `ChannelRegistry` and
  `IProviderConfigRepository`.
- **`DeliveryDispatcher`** (`delivery/dispatcher.py`) — one synchronous attempt per delivery. The
  provider call runs outside any transaction; each delivery gets its own transaction for the
  `in_progress`/final transitions and its Attempt. A raising provider becomes a non-retriable
  `unexpected` attempt (logged at ERROR). Owns attempt telemetry.
- **`IChannelProvider`** (`channel/ports.py`) — `prepare(message)` is the adapter's own validation
  seam (fills channel defaults, rejects a request the channel cannot carry) and
  `send(message) -> ProviderResult` normalizes the provider response. Adapters never decide
  retriability.
- **`classify()`** (`channel/classify.py`) — the one retriability rule: timeout/network, 420/429
  or any 5xx.
- **`ChannelRegistry`** (`channel/registry.py`) + **`provider_name_for`** (`channel/defaults.py`) —
  the `(channel, provider) → provider` map and the one table shared by validation and dispatch.
- **`AttemptTelemetry`** (`channel/telemetry.py`) — the attempt counter/histogram and the
  succeeded/failed events; 401/403 log at ERROR, never subject/body/recipient.
- **`IHealthChecker` / `IHealthGateway` / `HealthTelemetry`** (`health/`) — the scaffold's worked
  health example.
- **`ITransactionTemplate`** (`configuration/transaction.py`) and **`IClock`**
  (`commons/time.py`) — the transaction and time seams.
- Domain models are frozen, slotted dataclasses (see `CODING_STANDARDS.md`); Pydantic belongs
  only to `httpapi/schema.py` and `application/settings.py`.

### `persistence/` — SQLAlchemy 2 async adapters
**Purpose**: implements the `usecase` ports against MySQL and owns the transaction, the declarative
base and the naive-UTC conversion.
**Files**: `persistence/notification/{entity,repository}.py`;
`persistence/channel/{entity,repository}.py`;
`persistence/configuration/{base,database,transaction,timestamps}.py`;
`persistence/health/mysql_health_check.py`
**Seam(s)**:
- **`NotificationRepository`** (`notification/repository.py`) — `INotificationRepository` +
  `IDeliveryRepository`: create (notification + pending deliveries), get (with deliveries and
  attempts), get_delivery (one delivery + attempts), update_delivery, next_attempt_number (the
  append-only numbering the dispatcher uses), add_attempt (append-only), history
  (source/channel `EXISTS`/derived status/date filters, offset page + total).
- **`ProviderConfigRepository` / `RetryPolicyRepository`** (`channel/repository.py`) — one row per
  channel; retry policy is modeled now though v1 does not execute retries.
- **Transaction seam** — `SqlAlchemyTransactionTemplate` implements `ITransactionTemplate`;
  repositories call `current_session()`; nested `execute(...)` joins the outer transaction.
- **Entity seam** — entities on `configuration/base.py`'s `Base`, imported in `alembic/env.py`;
  `tests/integration/test_migrations.py` keeps entities and `0002_notification_hub` in lockstep.

### `gateway/` — outbound HTTP
**Purpose**: adapters for external systems, over one shared `httpx.AsyncClient`.
**Files**: `gateway/configuration/http_client.py`;
`gateway/email/mailgun_provider.py`; `gateway/health/{app_health_gateway,http_client_health_check}.py`
**Seam(s)**:
- **Client seam** — `build_http_client()` produces the single `AsyncClient` (5 s connect / 10 s
  read) the composition root injects everywhere, closes on shutdown, and adds an outbound
  `X-Request-ID` hook.
- **Mailgun adapter** (`email/mailgun_provider.py`) — form-encoded v3 send with basic
  `api:<key>`; `from`/`bcc` from provider config with `MAILGUN__*` fallback; `o:tracking=no`; both
  parts → multipart, one part → text-only or HTML-only; non-2xx and transport failures normalize
  to `ProviderResult`.
- **Health gateway** — `AppHealthGateway` calls the service's own `/health/internal`.

### `httpapi/` — FastAPI edge
**Purpose**: the HTTP surface — controllers, the edge DTOs, auth and the body guards, and the
domain-exception handlers.
**Files**: `httpapi/configuration/{server,telemetry,auth,guards}.py`;
`httpapi/controller/{base,health_controller,legacy_email_controller,notification_controller}.py`;
`httpapi/schema.py`; `httpapi/legacy_text.py`
**Seam(s)**:
- **Route seam** — `IController.router()` returns an `APIRouter`; `server.build_app` mounts every
  controller the composition root passes in.
- **`NotificationController`** (`controller/notification_controller.py`) — `POST /notifications`
  (Bearer + JSON/size guards, `201` + `Location` + the detail DTO), `GET /notifications` (query
  filters + offset page), `GET /notifications/{id}` (both reads share one representation) and
  `POST /deliveries/{id}/retry` (the delivery DTO after a synchronous attempt).
- **Auth seam** — `configuration/auth.py`'s `bearer_auth` dependency enforces
  `AUTH__API_TOKEN` with a constant-time compare; the router carries it, so `/send-email`,
  `/health*`, `/docs` and `/openapi.json` stay open.
- **Guard seam** — `configuration/guards.py` rejects a non-JSON body (`415`) and a body over
  1 MiB (`413`) before Pydantic sees it.
- **DTO seam** — Pydantic models in `schema.py` are the edge shape; a DTO change updates
  `frontend/src/api/types.ts` in the same commit. `UtcDateTime` serializes RFC 3339 `Z`.
- **Error seam** — `server._install_exception_handlers` maps domain exceptions and
  `RequestValidationError` to the `{code,detail,errors?}` envelope with body/query field paths;
  `DeliveryNotRetriableError` is the `409 conflict` branch, and a new domain exception is one
  handler branch there.
- **Legacy seam** — `legacy_email_controller.py` maps `/send-email` onto `NotificationService`
  and keeps the byte-for-byte contract (`legacy_text.py` derives its plain part).

### `application/` — composition root
**Purpose**: the one place that knows every concrete class — builds the object graph, telemetry,
the FastAPI app and the settings.
**Files**: `src/hablator/application/{settings,telemetry,container,boot}.py`
**Seam(s)**:
- **Composition seam** — `Container.__init__` builds telemetry first, then the engine, HTTP
  client, repositories, the channel registry (Mailgun), the dispatcher, the notification service,
  the controllers and the app; adding an adapter or endpoint is writing the class and adding one
  line there.
- **Config seam** — `Settings` reads `APP_ENV`, `HTTP_PORT`, `MYSQL__*`, `GATEWAYS__APP__HOST`,
  `MAILGUN__*` (`api_key` required), `AUTH__API_TOKEN` (required) and the `telemetry.*` keys.
  `DatabaseSettings` is the DB-only reader Alembic uses so a migration needs no app secret.
- **Entry seam** — `boot.py` exposes `app` and `main()`, serving on `HTTP_PORT` with reload only in
  `dev` and `--no-access-log`; tests build their own `Container` with fakes and a `FixedClock`.

### `tests/` — the two test lanes
**Purpose**: unit specs (no Docker) and integration specs that boot the real app against a real
MySQL and a stub Mailgun.
**Files**: `tests/conftest.py` (the `no_network` autouse guard); `tests/fixtures.py`;
`tests/unit/{test_notification_domain,test_channel_domain,test_notification_service,test_delivery_dispatcher,test_mailgun_provider,test_attempt_telemetry,test_settings,test_architecture,...}.py`;
`tests/integration/{conftest,test_notifications_api,test_notification_history_api,test_delivery_retry_api,test_notification_repository,test_notification_history,test_dispatch_transaction,test_legacy_send_email,test_migrations,...}.py`
**Seam(s)**: the HTTP boundary is the top seam (`test_notifications_api.py`,
`test_notification_history_api.py`, `test_delivery_retry_api.py`, `test_legacy_send_email.py`); repository ports are pinned against real MySQL; adapters run against
`pytest-httpserver`; services run with in-memory doubles. `no_network` rejects any non-loopback
connection, so no test can reach a real provider. `uv run poe check` is the Docker-free fast gate;
`uv run poe test` runs both lanes.

### `alembic/` + `scripts/` — the schema history
**Purpose**: the versioned schema and the script that applies it.
**Files**: `alembic.ini`; `alembic/env.py`; `alembic/script.py.mako`;
`alembic/versions/{0001_baseline,0002_notification_hub}.py`; `scripts/migrate.py`
**Seam(s)**: `env.py` imports every entity module for its side effect and builds the URL from
`DatabaseSettings`, so `alembic.ini` carries no URL. `scripts/migrate.py` runs `upgrade head` from
`deploy/entrypoint.sh`, never from the app's startup. `tests/integration/test_migrations.py` is
the drift guard.

### Lane root — packaging
**Purpose**: the toolchain and configuration around the package. The container, compose and CI
live at the repo root (one image, one workflow).
**Files**: `pyproject.toml`; `.env.example`; `docs/api.md`; `README.md`
**Seam(s)**: `pyproject.toml` carries every tool's config and the `poe` task graph — `poe check`
(lint, format-check, typecheck, contracts, unit tests) is the fast rung, and its `import-linter`
contracts are the layer gate. `poe migrate` / `poe migrate:generate` are the Alembic half.
`docs/api.md` is the consumer document.

## Entry points

- `src/hablator/application/boot.py` — the process: `app` is what uvicorn imports, `main()` runs
  uvicorn on `HTTP_PORT`; both build the `Container`.
- `src/hablator/httpapi/configuration/server.py` — `build_app` mounts the controllers and installs
  the exception handlers.
- `tests/integration/conftest.py` — the integration lane's entry: Testcontainers MySQL plus the
  real app over ASGI.
- The repo root's `Dockerfile` + `docker-compose.yml` — the container entry: uvicorn serves
  `hablator.application.boot:app`, with the MySQL sidecar.
