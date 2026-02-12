from __future__ import annotations

from typing import Optional, Any, Dict

from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import guess_entity_type
from .const import DOMAIN, TYPE_LIGHT

BRIGHTNESS_SCALE = 100

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    devices = data["devices"]
    coordinator = data["coordinator"]
    entity_types: Dict[str, str] = data.get("entity_types", {})

    ents = []
    for dev in devices:
        t = (entity_types.get(str(dev.did)) or guess_entity_type(dev.name)).lower()
        if t == TYPE_LIGHT:
            ents.append(ZenseLight(api, coordinator, dev.did, dev.name))
    async_add_entities(ents)

class ZenseLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, api, coordinator, did: int, name: str):
        self.api = api
        self.coordinator = coordinator
        self.did = did
        self._attr_name = f"{name} (Zense)"
        self._attr_unique_id = f"zensehome_light_{did}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        lvl = int(self.coordinator.data.get(self.did, 0))
        return lvl > 0

    @property
    def brightness(self) -> Optional[int]:
        lvl = self.coordinator.data.get(self.did)
        if lvl is None:
            return None
        lvl = max(0, min(BRIGHTNESS_SCALE, int(lvl)))
        return int(round((lvl / BRIGHTNESS_SCALE) * 255))

    async def async_turn_on(self, **kwargs: Any) -> None:
        bri = kwargs.get("brightness", 255)
        level = int(round((int(bri) / 255) * BRIGHTNESS_SCALE))
        level = max(1, min(BRIGHTNESS_SCALE, level))
        await self.api.fade(self.did, level, scale=BRIGHTNESS_SCALE)
        self.coordinator.data[self.did] = level
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.api.set_off(self.did)
        self.coordinator.data[self.did] = 0
        self.async_write_ha_state()

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
