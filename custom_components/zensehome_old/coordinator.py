from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZenseClient


@dataclass(frozen=True)
class ZenseDevice:
    did: int
    name: str


class ZenseCoordinator(DataUpdateCoordinator[dict[int, Optional[int]]]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: ZenseClient,
        devices: list[ZenseDevice],
        polling_seconds: int,
    ) -> None:
        self.client = client
        self.devices = devices
        super().__init__(
            hass=hass,
            logger=client.logger,
            name="zensehome_old",
            update_interval=timedelta(seconds=int(polling_seconds)),
        )

    async def _async_update_data(self) -> dict[int, Optional[int]]:
        try:
            ids = [d.did for d in self.devices]
            return await self.client.async_get_levels(self.hass, ids)
        except Exception as e:
            raise UpdateFailed(str(e)) from e
