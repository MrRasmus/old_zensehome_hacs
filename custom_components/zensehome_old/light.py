from __future__ import annotations

import asyncio
from typing import Optional

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ZenseClient
from .const import DOMAIN, DEFAULT_DEBOUNCE_S, BRIGHTNESS_SCALE, SWITCH_NAME_KEYWORDS
from .coordinator import ZenseCoordinator, ZenseDevice


def _raw_to_ha(raw: int) -> int:
    raw = max(0, min(BRIGHTNESS_SCALE, int(raw)))
    return int(round((raw / BRIGHTNESS_SCALE) * 255))


def _ha_to_raw(ha: int) -> int:
    ha = max(0, min(255, int(ha)))
    return int(round((ha / 255.0) * BRIGHTNESS_SCALE))


def _guess_is_switch(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in SWITCH_NAME_KEYWORDS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: ZenseClient = data["client"]
    coordinator: ZenseCoordinator = data["coordinator"]
    devices: list[ZenseDevice] = data["devices"]
    entity_map: dict[int, str] = data.get("entity_map", {})

    ents = []
    for dev in devices:
        mapped = entity_map.get(dev.did)
        if mapped == "switch":
            continue
        if mapped is None and _guess_is_switch(dev.name):
            continue
        ents.append(ZenseLight(entry, client, coordinator, dev))

    async_add_entities(ents)


class ZenseLight(CoordinatorEntity[ZenseCoordinator], LightEntity):
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        entry: ConfigEntry,
        client: ZenseClient,
        coordinator: ZenseCoordinator,
        dev: ZenseDevice,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.client = client
        self.dev = dev

        self._attr_name = f"{dev.name} (Zense)"
        self._attr_unique_id = f"{entry.entry_id}_{dev.did}_light"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZenseHome",
            "manufacturer": "Zense",
            "model": "TCP Controller",
        }

        self._debounce_s = float(DEFAULT_DEBOUNCE_S)
        self._pending_task: Optional[asyncio.Task] = None
        self._pending_level: Optional[int] = None

    @property
    def is_on(self) -> bool:
        lvl = (self.coordinator.data or {}).get(self.dev.did)
        return bool(lvl and lvl > 0)

    @property
    def brightness(self) -> Optional[int]:
        lvl = (self.coordinator.data or {}).get(self.dev.did)
        if lvl is None:
            return None
        return _raw_to_ha(lvl)

    async def async_turn_off(self, **kwargs) -> None:
        if self._pending_task:
            self._pending_task.cancel()
            self._pending_task = None
            self._pending_level = None

        await self.client.set_off(self.dev.did)

        data = dict(self.coordinator.data or {})
        data[self.dev.did] = 0
        self.coordinator.async_set_updated_data(data)

    async def async_turn_on(self, **kwargs) -> None:
        if ATTR_BRIGHTNESS not in kwargs:
            await self.client.set_on(self.dev.did)

            data = dict(self.coordinator.data or {})
            data[self.dev.did] = BRIGHTNESS_SCALE
            self.coordinator.async_set_updated_data(data)
            return

        raw = _ha_to_raw(int(kwargs[ATTR_BRIGHTNESS]))
        self._pending_level = raw
        if self._pending_task and not self._pending_task.done():
            return
        self._pending_task = asyncio.create_task(self._debounced_send())

    async def _debounced_send(self) -> None:
        try:
            await asyncio.sleep(self._debounce_s)
            lvl = self._pending_level
            self._pending_level = None
            if lvl is None:
                return

            if lvl <= 0:
                await self.client.set_off(self.dev.did)
                new_val = 0
            else:
                await self.client.fade(self.dev.did, lvl)
                new_val = lvl

            data = dict(self.coordinator.data or {})
            data[self.dev.did] = new_val
            self.coordinator.async_set_updated_data(data)
        except asyncio.CancelledError:
            return
