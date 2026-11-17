# Code map

Module → key files → seam index, plus the app entry points; seeded from the scaffold — re-author it with the `code-map` skill as the project's modules grow.

The layers are one package, `src/hablator/`, with one sub-package each; `import-linter` enforces that dependencies point inward (`application → httpapi/persistence/gateway → usecase`).

## Modules

### `usecase/` — domain models, ports and services
**Purpose**: the pure core. Owns the health-check ports (`IHealthChecker`, `IHealthGateway`), the `HealthCheckResult` model, the transaction port and the cross-cutting helpers. Imports no framework — `import-linter` forbids `fastapi`, `sqlalchemy`, `httpx`, `uvicorn` and `pydantic` here.
**Files**: `src/hablator/usecase/health/{checker,gateway,telemetry}.py`; `src/hablator/usecase/channel/{model,ports,classify,registry,telemetry}.py`; `src/hablator/usecase/notification/{model,ports,service}.py`; `src/hablator/usecase/delivery/{ports,dispatcher}.py`; `src/hablator/usecase/configuration/transaction.py`; `src/hablator/usecase/commons/{time,logging,request_context,asyncx,exceptions}.py`
**Seam(s)**:
- **`IHealthChecker`** (`health/checker.py`) — the inbound port (`async get_health_status() -> HealthCheckResult`); `HealthController` takes a `Sequence[IHealthChecker]` and every adapter satisfies it structurally.
- **`IHealthGateway`** (`health/gateway.py`) — the outbound port (`async is_healthy() -> bool`), implemented by `gateway`'s `AppHealthGateway` and consumed by `HttpClientHealthCheck`.
- **`HealthTelemetry`** (`health/telemetry.py`) — records the last result per component into `health.check.status`, increments `health.check.failures`, and logs only WARN/INFO transitions; `HealthController` calls `record(...)`.
- **`request_context`** (`commons/request_context.py`) — the `ContextVar` carrier for `request.id` / `job.id`; the edge binds it and the outbound client propagates it.
- **Log bridge** (`commons/logging.py`) — structlog stays the API, stdlib is the chokepoint; the terminal processor splits event/attributes, and the redaction filter stamps `event.name` on plain framework logs.
- **`ITransactionTemplate`** (`configuration/transaction.py`) — lets a service compose several repository writes atomically without importing SQLAlchemy; implemented in `persistence`.
- **`IClock`** (`commons/time.py`) — the time seam; logic reads time from the injected clock, never `datetime.now()`, so tests can fix it.
- **`IChannelProvider`** (`channel/ports.py`) — `channel` + `name` + `async send(ChannelMessage) -> ProviderResult`; adapters normalize errors and never decide retriability. `ChannelMessage` (channel-local, not `notification.Delivery`) keeps the slice DAG `delivery -> notification -> channel` acyclic.
- **`classify()`** (`channel/classify.py`) — the single retriability rule (`timeout`/`network`, 420/429, ≥500).
- **`ChannelRegistry`** (`channel/registry.py`) — the `(channel, provider name) -> provider` map built once in the composition root.
- **`AttemptTelemetry`** (`channel/telemetry.py`) — `notification.attempts` counter, `notification.attempt.duration` histogram and the `channel.attempt.*` events; never subject, body or recipient.
- **`NotificationService`** (`notification/service.py`) — persists the notification and one pending delivery per channel in one transaction through `INotificationRepository.create`, then fans the first attempt out; `IDeliveryDispatcher` is declared in `notification/ports.py` (where the service consumes it) and implemented in `delivery`.
- **`DeliveryDispatcher`** (`delivery/dispatcher.py`) — resolves the provider/config, marks `in_progress`, calls the provider **outside** any transaction, then records the attempt and the terminal status in a new transaction through `IDeliveryRepository` (`delivery/ports.py`); a raising provider becomes a non-retriable `unexpected` attempt.
- Domain models are frozen, slotted dataclasses (see `CODING_STANDARDS.md`); Pydantic belongs only to `httpapi/schema.py` and `application/settings.py`.

### `persistence/` — SQLAlchemy 2 async adapters
**Purpose**: implements the `usecase` ports against MySQL and owns the transaction hablator and the declarative base.
**Files**: `src/hablator/persistence/configuration/{base,database,transaction}.py`; `src/hablator/persistence/health/mysql_health_check.py`; `src/hablator/persistence/notification/{entity,repository}.py`; `src/hablator/persistence/channel/{entity,repository}.py`
**Seam(s)**:
- **Adapter seam** — `MySqlConnectionHealthCheck` is the worked example of a class satisfying `IHealthChecker`; `NotificationRepository` implements both `INotificationRepository.create` and `IDeliveryRepository` (`update_delivery`/`add_attempt`) the same way.
- **Transaction seam** — `SqlAlchemyTransactionTemplate` implements `ITransactionTemplate`; repositories call `current_session()` to get the session bound to the running transaction, and nested `execute(...)` calls join it.
- **Entity seam** — `configuration/base.py`'s `Base` is the declarative base; the five hub entities live in `notification/entity.py` (notification, delivery, attempt) and `channel/entity.py` (provider_config, retry_policy), are imported in `alembic/env.py`, and match `0002_notification_hub` (the migration guard asserts it).

### `gateway/` — outbound HTTP
**Purpose**: adapters for external systems, over one shared `httpx.AsyncClient`.
**Files**: `src/hablator/gateway/configuration/http_client.py`; `src/hablator/gateway/health/{app_health_gateway,http_client_health_check}.py`; `src/hablator/gateway/email/mailgun_provider.py`
**Seam(s)**:
- **Client seam** — `configuration/http_client.py`'s `build_http_client()` produces the single `AsyncClient` the composition root injects everywhere, closes on shutdown, and adds an outbound `X-Request-ID` request hook.
- **Gateway seam** — `AppHealthGateway` implements `IHealthGateway` by calling the service's own `/health/internal`; `HttpClientHealthCheck` implements `IHealthChecker` on top of that port. A new integration adds the port in `usecase` and its adapter here. `HTTPXClientInstrumentor` supplies `http.client.request.duration` on this shared client.
- **Email provider seam** — `MailgunEmailProvider` implements `IChannelProvider` for `Channel.EMAIL`: one v3 form-encoded call, `from`/`bcc` from provider config with env fallback, `o:tracking=no`, multipart when both parts exist; it normalizes timeout/network/HTTP failures into `ProviderResult` and keeps the raw body for the legacy response.

### `httpapi/` — FastAPI edge
**Purpose**: the HTTP surface — controllers, the edge DTOs and the domain-exception handlers.
**Files**: `src/hablator/httpapi/configuration/{server,telemetry}.py`; `src/hablator/httpapi/controller/{base,health_controller,legacy_email_controller}.py`; `src/hablator/httpapi/legacy_text.py`; `src/hablator/httpapi/schema.py`
**Seam(s)**:
- **Route seam** — `IController.router()` returns an `APIRouter`; `server.build_app` mounts every controller the composition root passes in, so adding an endpoint never edits the server wiring.
- **Request seam** — `server.RequestContextMiddleware` is added last (outermost): it validates/generates `X-Request-ID`, binds the `ContextVar`, echoes the response header, and owns the single 4xx WARN / 5xx ERROR boundary record. `configuration/telemetry.py` installs the FastAPI/ASGI instrumentation.
- **DTO seam** — Pydantic models in `schema.py` are the edge shape; in a generated project that also ships a frontend, a DTO change updates its `frontend/src/api/types.ts` in the same commit.
- **Error seam** — `server._install_exception_handlers` maps domain exceptions to the `{"code","detail"}` body and stamps `request.state.error_type`; a new domain exception is one handler branch there.
- **Legacy seam** — `LegacyEmailController` parses the legacy payload itself (so invalid JSON stays `400`, not FastAPI's `422`), maps it to `NotificationService`, and echoes the provider's raw body with `json.dumps` defaults for byte compatibility; `legacy_text.strip_html` derives the plain part only on this path.

### `application/` — composition root
**Purpose**: the one place that knows every concrete class — builds the object graph, telemetry, the FastAPI app and the settings.
**Files**: `src/hablator/application/{settings,telemetry,container,boot}.py`
**Seam(s)**:
- **Telemetry seam** — `telemetry.build_telemetry(settings)` builds the resource, providers, views and exporters (or in-memory ones for `APP_ENV=test`), then `Telemetry.instrument_*` installs runtime/engine/client/app instrumentation and the pool series. `Telemetry.shutdown()` flushes on `Container.aclose()`.
- **Composition seam** — `Container.__init__` builds telemetry first, injects `HealthTelemetry`/`Meter`, then the engine, HTTP client, checkers and controllers; adding a checker or endpoint is writing the class and adding one line there.
- **Config seam** — `Settings` (pydantic-settings) reads `APP_ENV`, `HTTP_PORT`, `MYSQL__*`, `GATEWAYS__APP__HOST`, the bare `API_URL` / `API_AUTH` / `FROM_EMAIL` / `BCC_EMAIL` email keys and the three `telemetry.*` keys from the standard `OTEL_*` / `TELEMETRY_CONSOLE` names; nested env vars use `__` as the delimiter. `Settings.app_host` derives the self-health base URL from `HTTP_PORT` unless `GATEWAYS__APP__HOST` is set explicitly.
- **Entry seam** — `boot.py` exposes `app` (the uvicorn import target) and `main()`, which serves on `HTTP_PORT` with reload only in `dev` and `--no-access-log`; tests build their own `Container` with fakes and a `FixedClock`.

### `tests/` — the two test lanes
**Purpose**: unit specs (no Docker) and integration specs that boot the real app against a real MySQL.
**Files**: `tests/conftest.py`; `tests/fixtures.py`; `tests/unit/{test_app_health_gateway,test_app_host,test_boot,test_telemetry,test_logging_bridge,test_health_telemetry,test_telemetry_http,test_channel_domain,test_notification_domain,test_legacy_text,test_mailgun_provider,test_delivery_dispatcher,test_notification_service}.py`; `tests/integration/conftest.py`; `tests/integration/{test_health,test_telemetry_db,test_migrations,test_notification_repository,test_legacy_send_email}.py`
**Seam(s)**: `tests/integration/conftest.py` starts MySQL through Testcontainers, applies the schema once, and drives the real app in-process over ASGI; unit specs construct fakes directly. `tests/fixtures.py` carries the shared in-memory repository, transaction, provider and config fakes. The legacy contract is pinned by `test_legacy_send_email.py` (valid/400/404/502/chunked/env-fallback, plus the outgoing form and the history rows) against a stub Mailgun server; `test_notification_repository.py` covers the port methods on real MySQL; `test_migrations.py` keeps the entities and `0002` in lockstep. The self-health base-URL derivation is pinned in `tests/unit/test_app_host.py`, and the module entrypoint's configured port and dev-only reload in `tests/unit/test_boot.py`. The telemetry contract is split by clause: `test_telemetry.py` (resource/config/runtime/pool), `test_logging_bridge.py` (record shape/correlation/redaction), `test_health_telemetry.py` (gauge/counter/transitions), and `test_telemetry_http.py` (ASGI boundary/catalog/buckets with a stub checker). `tests/integration/test_telemetry_db.py` is DB-backed extra evidence. Put a shared builder next to `tests/conftest.py` rather than copying fixtures per spec. `uv run poe check` is the Docker-free fast gate; the integration lane runs against a real MySQL.

### `alembic/` + `scripts/` — the schema history
**Purpose**: the versioned schema and the script that applies it.
**Files**: `alembic.ini`; `alembic/env.py`; `alembic/script.py.mako`; `alembic/versions/{0001_baseline,0002_notification_hub}.py`; `scripts/migrate.py`
**Seam(s)**: `env.py` is the seam between `Base.metadata` and the database — it imports every entity module for its side effect and builds the URL from `Settings().mysql.url`, so `alembic.ini` carries no URL. `scripts/migrate.py` runs `upgrade head` from `deploy/entrypoint.sh`, never from the app's startup. `tests/integration/test_migrations.py` is the drift guard: it migrates a throwaway MySQL and asserts `compare_metadata` is empty.

### Lane root — packaging
**Purpose**: the toolchain and configuration around the package. The container, compose and CI live at the repo root (one image, one workflow).
**Files**: `pyproject.toml`; `.env.example`; `README.md`
**Seam(s)**: `pyproject.toml` carries every tool's config and the `poe` task graph — `poe check` (lint, format-check, typecheck, contracts, unit tests) is the verification ladder's fast rung, and its `import-linter` contracts are the layer gate; `poe migrate` / `poe migrate:generate` are the Alembic half. The root `.pre-commit-config.yaml` runs the branch guard plus this lane's `poe check`.

## Entry points

- `src/hablator/application/boot.py` — the process: `app` is what uvicorn imports, `main()` runs uvicorn on `HTTP_PORT`; both build the `Container`.
- `src/hablator/httpapi/configuration/server.py` — `build_app` mounts the controllers and installs the exception handlers.
- `tests/integration/conftest.py` — the integration lane's entry: Testcontainers MySQL plus the real app over ASGI.
- The repo root's `Dockerfile` + `docker-compose.yml` — the container entry: uvicorn serves `hablator.application.boot:app`, with the MySQL sidecar.
