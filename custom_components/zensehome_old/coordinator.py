from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZenseApi, ZenseDevice
from .const import DOMAIN

class ZenseCoordinator(DataUpdateCoordinator[Dict[int, int]]):
    def __init__(self, hass: HomeAssistant, api: ZenseApi, devices: List[ZenseDevice], poll_minutes: int):
        super().__init__(
            hass=hass,
            logger=None,
            name=DOMAIN,
            update_interval=timedelta(minutes=max(1, int(poll_minutes))),
        )
        self.api = api
        self.devices = devices

    async def _async_update_data(self) -> Dict[int, int]:
        try:
            data: Dict[int, int] = {}
            for dev in self.devices:
                lvl = await self.api.get_level(dev.did)
                if lvl is not None:
                    data[dev.did] = int(lvl)
            return data
        except Exception as e:
            raise UpdateFailed(str(e)) from e
