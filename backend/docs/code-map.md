# Code map

Module → key files → seam index, plus the app entry points; seeded from the scaffold — re-author it with the `code-map` skill as the project's modules grow.

The layers are one package, `src/hablator/`, with one sub-package each; `import-linter` enforces that dependencies point inward (`application → httpapi/persistence/gateway → usecase`).

## Modules

### `usecase/` — domain models, ports and services
**Purpose**: the pure core. Owns the health-check ports, the hub's channel/notification/delivery vocabulary and ports, the transaction port and the cross-cutting helpers. Imports no framework — `import-linter` forbids `fastapi`, `sqlalchemy`, `httpx`, `uvicorn` and `pydantic` here.
**Files**: `src/hablator/usecase/health/{checker,gateway,telemetry}.py`; `src/hablator/usecase/channel/{model,provider,repository,retriability}.py`; `src/hablator/usecase/notification/{model,repository}.py`; `src/hablator/usecase/delivery/repository.py`; `src/hablator/usecase/configuration/transaction.py`; `src/hablator/usecase/commons/{time,logging,request_context,asyncx,exceptions}.py`
**Seam(s)**:
- **Channel vocabulary and the one port** (`channel/model.py`, `channel/provider.py`) — `Channel`, `Content`, `Recipient`, `ProviderConfig`, `RetryPolicy`, `ProviderResult` and `ErrorKind`; `IChannelProvider.send(OutboundDelivery) -> ProviderResult`; `ChannelRegistry` keyed by `(channel, provider)` rejects an unregistered pair with `UnknownProviderError`. `OutboundDelivery` is the narrow structural view a `Delivery` satisfies, so the channel slice never imports the notification slice.
- **Retriability** (`channel/retriability.py`) — `is_retriable(error_kind, provider_status)` is the single classification (timeout/network, 420/429, 5xx); adapters only normalize.
- **Notification aggregate** (`notification/model.py`) — `Notification`/`Delivery`/`Attempt` as frozen slotted dataclasses; `derive_notification_status` (derived, never persisted) and `transition` (the `pending -> in_progress -> succeeded | failed` lifecycle, with `next_attempt_at` on a return to pending).
- **Ports** (`notification/repository.py`, `delivery/repository.py`, `channel/repository.py`) — `INotificationRepository` (create/get/history), `IDeliveryRepository` (get/append_attempt/transition — no attempt update), `IProviderConfigRepository`, `IRetryPolicyRepository`, and `IDeliveryDispatcher` declared where the notification service will consume it.
- **Slice DAG** — `delivery -> notification -> channel` is enforced by the static test in `tests/unit/test_architecture.py`; `channel` imports neither sibling.
- **`IHealthChecker`** (`health/checker.py`) — the inbound port (`async get_health_status() -> HealthCheckResult`); `HealthController` takes a `Sequence[IHealthChecker]` and every adapter satisfies it structurally.
- **`IHealthGateway`** (`health/gateway.py`) — the outbound port (`async is_healthy() -> bool`), implemented by `gateway`'s `AppHealthGateway` and consumed by `HttpClientHealthCheck`.
- **`HealthTelemetry`** (`health/telemetry.py`) — records the last result per component into `health.check.status`, increments `health.check.failures`, and logs only WARN/INFO transitions; `HealthController` calls `record(...)`.
- **`request_context`** (`commons/request_context.py`) — the `ContextVar` carrier for `request.id` / `job.id`; the edge binds it and the outbound client propagates it.
- **Log bridge** (`commons/logging.py`) — structlog stays the API, stdlib is the chokepoint; the terminal processor splits event/attributes, and the redaction filter stamps `event.name` on plain framework logs.
- **`ITransactionTemplate`** (`configuration/transaction.py`) — lets a service compose several repository writes atomically without importing SQLAlchemy; implemented in `persistence`.
- **`IClock`** (`commons/time.py`) — the time seam; logic reads time from the injected clock, never `datetime.now()`, so tests can fix it.
- Domain models are frozen, slotted dataclasses (see `CODING_STANDARDS.md`); Pydantic belongs only to `httpapi/schema.py` and `application/settings.py`.

### `persistence/` — SQLAlchemy 2 async adapters
**Purpose**: implements the `usecase` ports against MySQL and owns the transaction template and the declarative base.
**Files**: `src/hablator/persistence/configuration/{base,database,transaction,timestamps,checks}.py`; `src/hablator/persistence/notification/{entity,mapping,notification_repository,delivery_repository}.py`; `src/hablator/persistence/channel/{entity,provider_config_repository,retry_policy_repository}.py`; `src/hablator/persistence/health/mysql_health_check.py`
**Seam(s)**:
- **Adapter seam** — `MySqlConnectionHealthCheck` is the worked example of a class satisfying `IHealthChecker`; the notification/delivery/provider-config/retry-policy repositories implement their `usecase` ports the same way.
- **Transaction seam** — `SqlAlchemyTransactionTemplate` implements `ITransactionTemplate`; repositories call `current_session()` to get the session bound to the running transaction, and nested `execute(...)` calls join it.
- **Entity seam** — `notification/entity.py` holds the `notification`/`delivery`/`attempt` entities and `channel/entity.py` the `provider_config`/`retry_policy` pair, all SQLAlchemy 2.0 typed `Mapped[...]`; `alembic/env.py` imports both for their metadata side effect, and `tests/integration/test_migrations.py` guards the drift.
- **Mapping seam** — `notification/mapping.py` is the single entity↔domain conversion, and `configuration/timestamps.py` is the single naive-UTC-at-the-DB / aware-UTC-in-the-domain boundary. A repository method takes `now` from the caller (the service's `IClock`), so persistence never reads the clock.

### `gateway/` — outbound HTTP
**Purpose**: adapters for external systems, over one shared `httpx.AsyncClient`.
**Files**: `src/hablator/gateway/configuration/http_client.py`; `src/hablator/gateway/health/{app_health_gateway,http_client_health_check}.py`
**Seam(s)**:
- **Client seam** — `configuration/http_client.py`'s `build_http_client()` produces the single `AsyncClient` the composition root injects everywhere, closes on shutdown, and adds an outbound `X-Request-ID` request hook.
- **Gateway seam** — `AppHealthGateway` implements `IHealthGateway` by calling the service's own `/health/internal`; `HttpClientHealthCheck` implements `IHealthChecker` on top of that port. A new integration adds the port in `usecase` and its adapter here. `HTTPXClientInstrumentor` supplies `http.client.request.duration` on this shared client.

### `httpapi/` — FastAPI edge
**Purpose**: the HTTP surface — controllers, the edge DTOs and the domain-exception handlers.
**Files**: `src/hablator/httpapi/configuration/{server,telemetry}.py`; `src/hablator/httpapi/controller/{base,health_controller}.py`; `src/hablator/httpapi/schema.py`
**Seam(s)**:
- **Route seam** — `IController.router()` returns an `APIRouter`; `server.build_app` mounts every controller the composition root passes in, so adding an endpoint never edits the server wiring.
- **Request seam** — `server.RequestContextMiddleware` is added last (outermost): it validates/generates `X-Request-ID`, binds the `ContextVar`, echoes the response header, and owns the single 4xx WARN / 5xx ERROR boundary record. `configuration/telemetry.py` installs the FastAPI/ASGI instrumentation.
- **DTO seam** — Pydantic models in `schema.py` are the edge shape; in a generated project that also ships a frontend, a DTO change updates its `frontend/src/api/types.ts` in the same commit.
- **Error seam** — `server._install_exception_handlers` maps domain exceptions to the `{"code","detail"}` body and stamps `request.state.error_type`; a new domain exception is one handler branch there.

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
**Files**: `tests/conftest.py`; `tests/fixtures.py`; `tests/docker_probe.py`; `tests/unit/{test_app_health_gateway,test_app_host,test_architecture,test_boot,test_channel_registry,test_docker_probe,test_harness_failure,test_notification_lifecycle,test_ports,test_retriability,test_telemetry,test_logging_bridge,test_health_telemetry,test_telemetry_http}.py`; `tests/integration/conftest.py`; `tests/integration/{test_health,test_telemetry_db,test_migrations,test_notification_repository,test_delivery_repository,test_provider_config_repository,test_retry_policy_repository,test_schema}.py`
**Seam(s)**: `tests/integration/conftest.py` probes Docker (`tests/docker_probe.py`; a missing daemon exits non-zero with an actionable message, never skips), starts MySQL 9.4.0 through Testcontainers, migrates it to head, and drives the real app in-process over ASGI; unit specs construct fakes directly. The self-health base-URL derivation is pinned in `tests/unit/test_app_host.py`, and the module entrypoint's configured port and dev-only reload in `tests/unit/test_boot.py`. The telemetry contract is split by clause: `test_telemetry.py` (resource/config/runtime/pool), `test_logging_bridge.py` (record shape/correlation/redaction), `test_health_telemetry.py` (gauge/counter/transitions), and `test_telemetry_http.py` (ASGI boundary/catalog/buckets with a stub checker). The hub's pure rules live in `test_retriability.py`, `test_channel_registry.py`, `test_notification_lifecycle.py` and the append-only port in `test_ports.py`; `test_architecture.py` enforces the OTel-API-only core and the `delivery -> notification -> channel` slice DAG. Each repository port method is pinned against real MySQL (`test_notification_repository`, `test_delivery_repository`, `test_provider_config_repository`, `test_retry_policy_repository`), the schema's checks/cascades in `test_schema.py`, and `test_telemetry_db.py` is DB-backed extra evidence. Put a shared builder next to `tests/conftest.py` rather than copying fixtures per spec. `uv run poe check` is the Docker-free fast gate; the integration lane runs against a real MySQL.

### `alembic/` + `scripts/` — the schema history
**Purpose**: the versioned schema and the script that applies it.
**Files**: `alembic.ini`; `alembic/env.py`; `alembic/script.py.mako`; `alembic/versions/{0001_baseline,0002_notification_hub}.py`; `scripts/migrate.py`
**Seam(s)**: `env.py` is the seam between `Base.metadata` and the database — it imports every entity module for its side effect and builds the URL from `Settings().mysql.url`, so `alembic.ini` carries no URL. `0002_notification_hub` is the hub's five tables (notification, delivery, attempt, provider_config, retry_policy). `scripts/migrate.py` runs `upgrade head` from `deploy/entrypoint.sh`, never from the app's startup. `tests/integration/test_migrations.py` is the drift guard: it migrates a throwaway MySQL and asserts `compare_metadata` is empty.

### Lane root — packaging
**Purpose**: the toolchain and configuration around the package. The container, compose and CI live at the repo root (one image, one workflow).
**Files**: `pyproject.toml`; `.env.example`; `README.md`
**Seam(s)**: `pyproject.toml` carries every tool's config and the `poe` task graph — `poe check` (lint, format-check, typecheck, contracts, unit tests) is the verification ladder's fast rung, and its `import-linter` contracts are the layer gate; `poe migrate` / `poe migrate:generate` are the Alembic half. The root `.pre-commit-config.yaml` runs the branch guard plus this lane's `poe check`.

## Entry points

- `src/hablator/application/boot.py` — the process: `app` is what uvicorn imports, `main()` runs uvicorn on `HTTP_PORT`; both build the `Container`.
- `src/hablator/httpapi/configuration/server.py` — `build_app` mounts the controllers and installs the exception handlers.
- `tests/integration/conftest.py` — the integration lane's entry: Testcontainers MySQL plus the real app over ASGI.
- The repo root's `Dockerfile` + `docker-compose.yml` — the container entry: uvicorn serves `hablator.application.boot:app`, with the MySQL sidecar.
