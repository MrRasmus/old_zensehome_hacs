from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SWITCH_NAME_KEYWORDS
from .coordinator import ZenseCoordinator, ZenseDevice
from .api import ZenseClient


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
        if mapped == "light":
            continue
        if mapped == "switch" or (mapped is None and _guess_is_switch(dev.name)):
            ents.append(ZenseSwitch(hass, entry, client, coordinator, dev))

    async_add_entities(ents)


class ZenseSwitch(SwitchEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ZenseClient,
        coordinator: ZenseCoordinator,
        dev: ZenseDevice,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.coordinator = coordinator
        self.dev = dev

        self._attr_name = f"{dev.name} (Zense)"
        self._attr_unique_id = f"{entry.entry_id}_{dev.did}_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZenseHome",
            "manufacturer": "Zense",
            "model": "TCP Controller",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        lvl = self.coordinator.data.get(self.dev.did)
        return bool(lvl and lvl > 0)

    async def async_turn_off(self, **kwargs) -> None:
        await self.client.set_off(self.dev.did)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.set_on(self.dev.did)
        await self.coordinator.async_request_refresh()
