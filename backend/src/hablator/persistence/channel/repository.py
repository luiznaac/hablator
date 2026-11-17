"""`ProviderConfigRepository` — reads a channel's non-secret provider config from the database."""

from __future__ import annotations

from hablator.persistence.channel.entity import ProviderConfigEntity
from hablator.persistence.configuration.transaction import current_session
from hablator.usecase.channel.model import Channel, ProviderConfig


class ProviderConfigRepository:
    async def get(self, channel: Channel) -> ProviderConfig | None:
        session = current_session()
        entity = await session.get(ProviderConfigEntity, str(channel))
        if entity is None:
            return None
        return ProviderConfig(
            channel=Channel(entity.channel),
            provider=entity.provider,
            config=dict(entity.config),
        )
