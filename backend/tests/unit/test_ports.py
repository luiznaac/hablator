"""Port shape rules: attempts are append-only, so the delivery port exposes no attempt update."""

from __future__ import annotations

from hablator.usecase.delivery.ports import IDeliveryRepository


def test_delivery_repository_port_has_no_attempt_update() -> None:
    methods = {name for name in dir(IDeliveryRepository) if not name.startswith("_")}

    assert methods == {"update_delivery", "add_attempt"}
    assert not any("attempt" in name and "update" in name for name in methods)
