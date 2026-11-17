"""`GET /notifications` at the HTTP boundary: page shape, filters, ordering and bounds.

Rows are inserted directly so the test controls `created_at` and every delivery status; the real
app, the real MySQL and the real query stack are exercised.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fixtures import API_AUTH, insert_notification

_NOW = datetime(2026, 1, 1, 12, 0, 0)
_PIVOT = "2026-01-01T12:01:00Z"
_Deliveries = Sequence[tuple[str, str]]


async def _insert(
    engine: AsyncEngine,
    *,
    created_at: datetime = _NOW,
    source: str | None = "valoab",
    subject: str = "Backup finished",
    deliveries: _Deliveries = (("email", "succeeded"),),
) -> int:
    notification_id, _ = await insert_notification(
        engine,
        created_at=created_at,
        source=source,
        subject=subject,
        deliveries=deliveries,
    )
    return notification_id


async def _page(api_client: httpx.AsyncClient, query: str = "") -> dict[str, Any]:
    response = await api_client.get(f"/notifications{query}", headers=API_AUTH)
    assert response.status_code == 200
    return response.json()


def _ids(body: dict[str, Any]) -> list[int]:
    return [item["id"] for item in body["items"]]


async def test_the_default_page_shape_defaults_and_newest_first_order(
    api_client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    first = await _insert(engine, created_at=_NOW, subject="first")
    second = await _insert(engine, created_at=_NOW + timedelta(minutes=1), subject="second")
    third = await _insert(engine, created_at=_NOW + timedelta(minutes=2), subject="third")

    body = await _page(api_client)

    assert set(body) == {"items", "total", "limit", "offset"}
    assert (body["total"], body["limit"], body["offset"]) == (3, 20, 0)
    assert _ids(body) == [third, second, first]
    item = body["items"][0]
    assert set(item) == {"id", "source", "subject", "status", "created_at", "channels"}
    assert item["source"] == "valoab"
    assert item["subject"] == "third"
    assert item["status"] == "succeeded"
    assert item["created_at"].endswith("Z")
    assert item["channels"] == ["email"]


async def test_rows_with_the_same_instant_order_by_id_descending(
    api_client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    first = await _insert(engine)
    second = await _insert(engine)

    body = await _page(api_client)

    assert _ids(body) == [second, first]


async def test_offset_pagination_keeps_the_filtered_total(api_client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    first = await _insert(engine, created_at=_NOW)
    second = await _insert(engine, created_at=_NOW + timedelta(minutes=1))
    await _insert(engine, created_at=_NOW + timedelta(minutes=2))

    body = await _page(api_client, "?limit=1&offset=1")

    assert (body["total"], body["limit"], body["offset"]) == (3, 1, 1)
    assert _ids(body) == [second]
    assert first not in _ids(body)


@pytest.mark.parametrize(
    ("query", "field"),
    [("?limit=0", "limit"), ("?limit=101", "limit"), ("?offset=-1", "offset")],
)
async def test_a_page_bound_violation_is_422_validation_error_with_the_field(
    api_client: httpx.AsyncClient, query: str, field: str
) -> None:
    response = await api_client.get(f"/notifications{query}", headers=API_AUTH)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"][0]["field"] == field


async def test_an_unknown_channel_filter_is_422_validation_error(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/notifications?channel=carrier-pigeon", headers=API_AUTH)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_the_source_filter_is_exact(api_client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    valoab = await _insert(engine, source="valoab")
    await _insert(engine, source="chameidor")

    body = await _page(api_client, "?source=valoab")

    assert body["total"] == 1
    assert _ids(body) == [valoab]


async def test_the_channel_filter_is_a_delivery_exists(api_client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    both = await _insert(engine, deliveries=(("email", "succeeded"), ("push", "succeeded")))
    await _insert(engine, deliveries=(("email", "succeeded"),))

    body = await _page(api_client, "?channel=push")

    assert body["total"] == 1
    assert _ids(body) == [both]
    assert body["items"][0]["channels"] == ["email", "push"]


async def test_the_status_filter_reads_the_derived_aggregate(
    api_client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    succeeded = await _insert(engine, deliveries=(("email", "succeeded"), ("push", "succeeded")))
    failed = await _insert(engine, deliveries=(("email", "failed"), ("push", "succeeded")))
    pending = await _insert(engine, deliveries=(("email", "succeeded"), ("push", "pending")))

    succeeded_page = await _page(api_client, "?status=succeeded")
    failed_page = await _page(api_client, "?status=failed")
    pending_page = await _page(api_client, "?status=pending")

    assert _ids(succeeded_page) == [succeeded]
    assert _ids(failed_page) == [failed]
    assert _ids(pending_page) == [pending]


async def test_the_date_filters_are_inclusive_after_and_exclusive_before(
    api_client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    earlier = await _insert(engine, created_at=_NOW)
    pivot = await _insert(engine, created_at=_NOW + timedelta(minutes=1))
    later = await _insert(engine, created_at=_NOW + timedelta(minutes=2))

    after = await _page(api_client, f"?created_after={_PIVOT}")
    before = await _page(api_client, f"?created_before={_PIVOT}")

    assert _ids(after) == [later, pivot]
    assert _ids(before) == [earlier]


async def test_a_combined_filter_narrows_to_one_row(api_client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    target = await _insert(
        engine,
        created_at=_NOW + timedelta(minutes=1),
        source="valoab",
        deliveries=(("email", "failed"), ("push", "failed")),
    )
    await _insert(engine, created_at=_NOW, source="valoab", deliveries=(("email", "failed"),))
    await _insert(
        engine,
        created_at=_NOW + timedelta(minutes=1),
        source="chameidor",
        deliveries=(("push", "failed"),),
    )
    await _insert(
        engine,
        created_at=_NOW + timedelta(minutes=1),
        source="valoab",
        deliveries=(("email", "succeeded"), ("push", "succeeded")),
    )

    body = await _page(
        api_client,
        "?source=valoab&channel=push&status=failed"
        "&created_after=2026-01-01T12:00:30Z&created_before=2026-01-01T12:01:30Z",
    )

    assert body["total"] == 1
    assert _ids(body) == [target]


async def test_an_empty_result_is_an_empty_page(api_client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _insert(engine)

    body = await _page(api_client, "?source=missing&limit=5&offset=2")

    assert body == {"items": [], "total": 0, "limit": 5, "offset": 2}


async def test_history_requires_the_bearer(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/notifications")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["code"] == "unauthorized"
