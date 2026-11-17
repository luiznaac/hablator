"""`DeliveryDispatcher` — one synchronous attempt per delivery, provider call outside the transaction.

Each delivery gets its own transactions for the status transitions and the Attempt; the provider
call itself runs with no session bound, so a slow provider never holds a database transaction open.
"""

from __future__ import annotations

from datetime import datetime

from hablator.usecase.channel.classify import classify
from hablator.usecase.channel.model import Channel, ChannelMessage, ErrorKind, ProviderResult
from hablator.usecase.channel.ports import IChannelProvider, IProviderConfigRepository
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.channel.telemetry import AttemptTelemetry
from hablator.usecase.commons.exceptions import DomainError
from hablator.usecase.commons.logging import get_logger
from hablator.usecase.commons.time import IClock
from hablator.usecase.configuration.transaction import ITransactionTemplate
from hablator.usecase.delivery.ports import IDeliveryRepository
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    Delivery,
    DeliveryOutcome,
    DeliveryStatus,
    transition,
)

_log = get_logger(__name__)

_DEFAULT_PROVIDERS: dict[Channel, str] = {Channel.EMAIL: "mailgun"}


class DeliveryDispatcher:
    def __init__(
        self,
        *,
        clock: IClock,
        transaction: ITransactionTemplate,
        repository: IDeliveryRepository,
        provider_configs: IProviderConfigRepository,
        registry: ChannelRegistry,
        telemetry: AttemptTelemetry | None = None,
    ) -> None:
        self._clock = clock
        self._transaction = transaction
        self._repository = repository
        self._provider_configs = provider_configs
        self._registry = registry
        self._telemetry = telemetry

    async def dispatch(self, delivery: Delivery) -> DeliveryOutcome:
        provider_name, provider_config = await self._resolve_provider(delivery.channel)
        provider = self._registry.resolve(delivery.channel, provider_name)

        in_progress = transition(delivery, DeliveryStatus.IN_PROGRESS, now=self._clock.now())
        await self._transaction.execute(lambda: self._repository.update_delivery(in_progress))

        result = await self._attempt(provider, provider_name, delivery, provider_config)

        finished_at = self._clock.now()
        attempt = self._record_attempt(delivery, result, in_progress.updated_at, finished_at)
        succeeded = result.is_success
        final = transition(
            in_progress,
            DeliveryStatus.SUCCEEDED if succeeded else DeliveryStatus.FAILED,
            now=finished_at,
        )
        await self._transaction.execute(lambda: self._persist_attempt(attempt, final))

        if self._telemetry is not None:
            self._telemetry.record(
                channel=delivery.channel,
                provider=result.provider,
                succeeded=succeeded,
                retriable=attempt.retriable,
                provider_status=result.provider_status,
                error_kind=result.error_kind,
                delivery_id=delivery.id,
                duration_seconds=(finished_at - in_progress.updated_at).total_seconds(),
            )
        return DeliveryOutcome(delivery=final, attempts=(attempt,), provider_body=result.provider_body)

    async def _resolve_provider(self, channel: Channel) -> tuple[str, dict[str, object]]:
        config = await self._transaction.execute(lambda: self._provider_configs.get(channel))
        if config is not None:
            return config.provider, dict(config.config)
        default = _DEFAULT_PROVIDERS.get(channel)
        if default is None:
            raise DomainError(f"Channel '{channel}' has no configured provider")
        return default, {}

    async def _attempt(
        self,
        provider: IChannelProvider,
        provider_name: str,
        delivery: Delivery,
        provider_config: dict[str, object],
    ) -> ProviderResult:
        message = ChannelMessage(
            channel=delivery.channel,
            recipients=delivery.recipients,
            content=delivery.content,
            options=delivery.options,
            config=provider_config,
        )
        try:
            return await provider.send(message)
        except Exception as error:
            _log.error(
                "channel.attempt.unexpected",
                exc_info=error,
                channel=str(delivery.channel),
                provider=provider_name,
                delivery_id=delivery.id,
            )
            return ProviderResult(
                provider=provider_name,
                provider_status=None,
                error_kind=ErrorKind.UNEXPECTED,
                error_message=str(error),
                provider_body="",
            )

    def _record_attempt(
        self,
        delivery: Delivery,
        result: ProviderResult,
        started_at: datetime,
        finished_at: datetime,
    ) -> Attempt:
        return Attempt(
            id=None,
            delivery_id=delivery.id,
            attempt_number=1,
            outcome=AttemptOutcome.SUCCEEDED if result.is_success else AttemptOutcome.FAILED,
            provider=result.provider,
            provider_status=result.provider_status,
            error_kind=result.error_kind,
            error_message=result.error_message,
            retriable=classify(result),
            started_at=started_at,
            finished_at=finished_at,
        )

    async def _persist_attempt(self, attempt: Attempt, delivery: Delivery) -> None:
        await self._repository.add_attempt(attempt)
        await self._repository.update_delivery(delivery)
