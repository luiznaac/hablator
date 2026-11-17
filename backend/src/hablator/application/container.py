"""Composition root — the hand-written replacement for Spring's component scan.

This is the ONE place that knows every concrete class. It builds the object
graph once at startup, builds telemetry first, injects the meter and applies
the instrumentation, and exposes:

* `health_checkers` — every `IHealthChecker` implementation (like `Set<HealthChecker>`)
* `controllers`     — every `IController` implementation (like `Set<ControllerTemplate>`)
* `app`             — the wired FastAPI application

Tests build their own `Container` with fakes / a `FixedClock` and never touch
global state.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from hablator.application.settings import Settings
from hablator.application.telemetry import Telemetry, build_telemetry
from hablator.gateway.configuration.http_client import build_http_client
from hablator.gateway.email.mailgun_provider import MailgunEmailProvider
from hablator.gateway.health.app_health_gateway import AppHealthGateway
from hablator.gateway.health.http_client_health_check import HttpClientHealthCheck
from hablator.gateway.push.ntfy_provider import NtfyPushProvider
from hablator.httpapi.configuration.server import build_app, install_request_context_middleware
from hablator.httpapi.controller.base import IController
from hablator.httpapi.controller.channel_controller import ChannelController
from hablator.httpapi.controller.health_controller import HealthController
from hablator.httpapi.controller.legacy_email_controller import LegacyEmailController
from hablator.httpapi.controller.notification_controller import NotificationController
from hablator.persistence.channel.repository import ProviderConfigRepository, RetryPolicyRepository
from hablator.persistence.configuration.database import build_engine, build_session_factory
from hablator.persistence.configuration.transaction import SqlAlchemyTransactionTemplate
from hablator.persistence.health.mysql_health_check import MySqlConnectionHealthCheck
from hablator.persistence.notification.repository import NotificationRepository
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.channel.service import ChannelConfigService
from hablator.usecase.channel.telemetry import AttemptTelemetry
from hablator.usecase.commons.time import IClock, SystemClock
from hablator.usecase.delivery.dispatcher import DeliveryDispatcher
from hablator.usecase.health.checker import IHealthChecker
from hablator.usecase.health.telemetry import HealthTelemetry
from hablator.usecase.notification.service import NotificationService


class Container:
    def __init__(
        self,
        settings: Settings,
        *,
        clock: IClock | None = None,
        telemetry: Telemetry | None = None,
        health_checkers: Sequence[IHealthChecker] | None = None,
    ) -> None:
        self.settings = settings
        self.clock: IClock = clock or SystemClock()
        self.telemetry: Telemetry = telemetry or build_telemetry(settings)

        # --- infrastructure singletons -------------------------------------
        self.engine: AsyncEngine = build_engine(settings.mysql.url)
        self.telemetry.instrument_engine(self.engine)
        self._session_factory = build_session_factory(self.engine)
        self.transaction_template = SqlAlchemyTransactionTemplate(self._session_factory)
        self.http_client: httpx.AsyncClient = build_http_client()
        self.telemetry.instrument_http_client()

        # --- health slice ------------------------------------------------
        self.health_telemetry = HealthTelemetry(self.telemetry.meter)
        if health_checkers is None:
            self._app_health_gateway = AppHealthGateway(self.http_client, settings.app_host)
            self.health_checkers: list[IHealthChecker] = [
                MySqlConnectionHealthCheck(self.engine, self.clock),
                HttpClientHealthCheck(self._app_health_gateway, self.clock),
            ]
        else:
            self.health_checkers = list(health_checkers)

        # --- channel / notification slice -------------------------------
        self.channel_registry = ChannelRegistry()
        self.channel_registry.register(
            MailgunEmailProvider(
                self.http_client,
                api_url=settings.mailgun.api_url,
                api_key=settings.mailgun.api_key,
                from_email=settings.mailgun.from_email,
                bcc_email=settings.mailgun.bcc_email,
            )
        )
        self.channel_registry.register(
            NtfyPushProvider(
                self.http_client,
                base_url=settings.ntfy.base_url,
                token=settings.ntfy.token,
            )
        )
        self.attempt_telemetry = AttemptTelemetry(self.telemetry.meter)
        self.notification_repository = NotificationRepository()
        self.provider_config_repository = ProviderConfigRepository()
        self.retry_policy_repository = RetryPolicyRepository()
        self.delivery_dispatcher = DeliveryDispatcher(
            clock=self.clock,
            transaction=self.transaction_template,
            repository=self.notification_repository,
            provider_configs=self.provider_config_repository,
            registry=self.channel_registry,
            telemetry=self.attempt_telemetry,
        )
        self.notification_service = NotificationService(
            clock=self.clock,
            transaction=self.transaction_template,
            repository=self.notification_repository,
            dispatcher=self.delivery_dispatcher,
            registry=self.channel_registry,
            provider_configs=self.provider_config_repository,
        )
        self.channel_config_service = ChannelConfigService(
            clock=self.clock,
            transaction=self.transaction_template,
            repository=self.provider_config_repository,
            registry=self.channel_registry,
        )

        # --- http layer ------------------------------------------------
        self.controllers: list[IController] = [
            HealthController(self.health_checkers, self.health_telemetry),
            LegacyEmailController(self.notification_service),
            NotificationController(self.notification_service, api_token=settings.auth.api_token),
            ChannelController(self.channel_config_service, api_token=settings.auth.api_token),
        ]

        @asynccontextmanager
        async def lifespan(_: FastAPI) -> AsyncIterator[None]:
            yield
            await self.aclose()

        self.app = build_app(self.controllers, lifespan=lifespan)
        self.telemetry.instrument_app(self.app)
        install_request_context_middleware(self.app)
        self.telemetry.instrument_runtime()

    async def aclose(self) -> None:
        await self.http_client.aclose()
        await self.engine.dispose()
        await self.telemetry.async_shutdown()
