"""Entity <-> domain mapping for the notification aggregate — the one place both repositories convert."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import inspect as sa_inspect

from hablator.persistence.configuration.timestamps import from_db_utc, to_db_utc
from hablator.persistence.notification.entity import AttemptEntity, DeliveryEntity, NotificationEntity
from hablator.usecase.channel.model import Channel, Content, ErrorKind, Recipient
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    Delivery,
    DeliveryStatus,
    NewDelivery,
    NewNotification,
    Notification,
)


def attempt_from_entity(entity: AttemptEntity) -> Attempt:
    return Attempt(
        attempt_number=entity.attempt_number,
        outcome=AttemptOutcome(entity.outcome),
        provider=entity.provider,
        provider_status=entity.provider_status,
        error_kind=ErrorKind(entity.error_kind) if entity.error_kind is not None else None,
        error_message=entity.error_message,
        retriable=bool(entity.retriable),
        started_at=from_db_utc(entity.started_at),
        finished_at=from_db_utc(entity.finished_at) if entity.finished_at is not None else None,
    )


def attempt_entity(delivery_id: int, attempt: Attempt) -> AttemptEntity:
    return AttemptEntity(
        delivery_id=delivery_id,
        attempt_number=attempt.attempt_number,
        outcome=attempt.outcome.value,
        provider=attempt.provider,
        provider_status=attempt.provider_status,
        error_kind=attempt.error_kind.value if attempt.error_kind is not None else None,
        error_message=attempt.error_message,
        retriable=attempt.retriable,
        started_at=to_db_utc(attempt.started_at),
        finished_at=to_db_utc(attempt.finished_at) if attempt.finished_at is not None else None,
    )


def _loaded_attempts(entity: DeliveryEntity) -> Sequence[AttemptEntity]:
    """A freshly created delivery has no attempts; a read one must have them eagerly loaded."""
    if "attempts" in sa_inspect(entity).unloaded:
        return ()
    return entity.attempts


def delivery_from_entity(entity: DeliveryEntity) -> Delivery:
    return Delivery(
        id=entity.id,
        notification_id=entity.notification_id,
        channel=Channel(entity.channel),
        recipients=tuple(Recipient(address) for address in entity.recipients),
        content=Content(subject=entity.subject, body=entity.body_text, body_html=entity.body_html),
        options=dict(entity.options),
        status=DeliveryStatus(entity.status),
        next_attempt_at=from_db_utc(entity.next_attempt_at) if entity.next_attempt_at is not None else None,
        created_at=from_db_utc(entity.created_at),
        updated_at=from_db_utc(entity.updated_at),
        attempts=tuple(attempt_from_entity(attempt) for attempt in _loaded_attempts(entity)),
    )


def delivery_entity(new: NewDelivery, now: datetime) -> DeliveryEntity:
    return DeliveryEntity(
        channel=new.channel.value,
        status=DeliveryStatus.PENDING.value,
        recipients=[recipient.address for recipient in new.recipients],
        subject=new.content.subject,
        body_text=new.content.body,
        body_html=new.content.body_html,
        options=dict(new.options),
        next_attempt_at=None,
        created_at=to_db_utc(now),
        updated_at=to_db_utc(now),
    )


def notification_entity(new: NewNotification, now: datetime) -> NotificationEntity:
    entity = NotificationEntity(
        source=new.source,
        subject=new.content.subject,
        body_text=new.content.body,
        body_html=new.content.body_html,
        created_at=to_db_utc(now),
    )
    entity.deliveries = [delivery_entity(delivery, now) for delivery in new.deliveries]
    return entity


def notification_from_entity(entity: NotificationEntity) -> Notification:
    return Notification(
        id=entity.id,
        source=entity.source,
        content=Content(subject=entity.subject, body=entity.body_text, body_html=entity.body_html),
        created_at=from_db_utc(entity.created_at),
        deliveries=tuple(delivery_from_entity(delivery) for delivery in entity.deliveries),
    )
