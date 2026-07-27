from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZenseClient
from .const import DOMAIN, DEFAULT_PAUSE_SECONDS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: ZenseClient = data["client"]

    async_add_entities([ZensePauseButton(entry, client)])


class ZensePauseButton(ButtonEntity):
    def __init__(self, entry: ConfigEntry, client: ZenseClient) -> None:
        self.entry = entry
        self.client = client

        self._attr_name = "Pause Zense 5 min"
        self._attr_unique_id = f"{entry.entry_id}_pause_5_min"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZenseHome",
            "manufacturer": "Zense",
            "model": "TCP Controller",
        }

    async def async_press(self) -> None:
        self.client.pause_for(DEFAULT_PAUSE_SECONDS)
