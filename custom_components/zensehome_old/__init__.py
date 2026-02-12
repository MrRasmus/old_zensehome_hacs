from __future__ import annotations

import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_HOST,
    CONF_PORT,
    CONF_CODE,
    CONF_POLLING_MINUTES,
    CONF_ENTITY_TYPES_JSON,
    DEFAULT_POLLING_MINUTES,
)
from .coordinator import ZenseCoordinator, ZenseDevice
from .api import ZenseClient


def _parse_entity_map(entry: ConfigEntry) -> dict[int, str]:
    s = (entry.options.get(CONF_ENTITY_TYPES_JSON) or "").strip()
    if not s:
        return {}
    try:
        data = json.loads(s)
        if not isinstance(data, dict):
            return {}
        out: dict[int, str] = {}
        for k, v in data.items():
            try:
                did = int(str(k).strip())
            except Exception:
                continue
            t = str(v).lower().strip()
            if t in ("light", "switch"):
                out[did] = t
        return out
    except Exception:
        return {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    code = entry.data[CONF_CODE]

    polling_minutes = int(entry.options.get(CONF_POLLING_MINUTES, DEFAULT_POLLING_MINUTES))
    polling_seconds = max(30, polling_minutes * 60)

    client = ZenseClient(host, port, code)
    devices_map = await client.async_get_devices_and_names(hass)
    devices = [ZenseDevice(did=k, name=v) for k, v in sorted(devices_map.items())]

    coordinator = ZenseCoordinator(hass, client, devices, polling_seconds)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "devices": devices,
        "entity_map": _parse_entity_map(entry),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok
