"""The migration's check constraints and cascades, exercised through raw SQL."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from hablator.application.container import Container
from tests.fixtures import attempt, create_notification


@pytest.mark.parametrize(
    ("channel", "status", "constraint"),
    [("fax", "pending", "ck_delivery_channel"), ("email", "bogus", "ck_delivery_status")],
)
async def test_check_constraints_reject_unknown_channels_and_statuses(
    repositories: Container, channel: str, status: str, constraint: str
) -> None:
    notification_id = (await create_notification(repositories)).id

    with pytest.raises(OperationalError, match=constraint):
        async with repositories.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO delivery "
                    "(notification_id, channel, status, recipients, body_text, created_at, updated_at) "
                    "VALUES (:notification_id, :channel, :status, JSON_ARRAY('ops@example.com'), "
                    "'body', NOW(6), NOW(6))"
                ),
                {"notification_id": notification_id, "channel": channel, "status": status},
            )


async def test_deleting_a_notification_cascades_to_deliveries_and_attempts(repositories: Container) -> None:
    notification = await create_notification(repositories)
    delivery_id = notification.deliveries[0].id
    await repositories.delivery_repository.append_attempt(delivery_id, attempt())

    async with repositories.engine.begin() as conn:
        await conn.execute(text("DELETE FROM notification WHERE id = :id"), {"id": notification.id})
        deliveries = await conn.scalar(
            text("SELECT COUNT(*) FROM delivery WHERE notification_id = :id"), {"id": notification.id}
        )
        attempts = await conn.scalar(text("SELECT COUNT(*) FROM attempt WHERE delivery_id = :id"), {"id": delivery_id})

    assert deliveries == 0
    assert attempts == 0
