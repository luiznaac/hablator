"""Port shape rules: attempts are append-only, so the delivery port exposes no update."""

from __future__ import annotations

from hablator.usecase.delivery.repository import IDeliveryRepository


def test_delivery_repository_port_has_no_attempt_update() -> None:
    methods = {name for name in dir(IDeliveryRepository) if not name.startswith("_")}

    assert methods == {"get", "append_attempt", "transition"}
