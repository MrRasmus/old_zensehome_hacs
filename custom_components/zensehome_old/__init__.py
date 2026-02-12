from __future__ import annotations

import json
from typing import Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import ZenseApi
from .coordinator import ZenseCoordinator
from .const import DOMAIN, PLATFORMS, CONF_HOST, CONF_PORT, CONF_CODE, DEFAULT_POLL_MIN, OPT_POLL_MIN, OPT_ENTITY_TYPES

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    code = entry.data[CONF_CODE]

    poll_minutes = entry.options.get(OPT_POLL_MIN, DEFAULT_POLL_MIN)
    types_json = entry.options.get(OPT_ENTITY_TYPES, "{}")
    try:
        entity_types: Dict[str, str] = json.loads(types_json) if types_json else {}
        if not isinstance(entity_types, dict):
            entity_types = {}
    except Exception:
        entity_types = {}

    api = ZenseApi(host=host, port=port, code=code)
    devices = await api.discover()

    coordinator = ZenseCoordinator(hass, api, devices, poll_minutes)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "devices": devices,
        "coordinator": coordinator,
        "entity_types": entity_types,  # {"57541": "switch"}
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
