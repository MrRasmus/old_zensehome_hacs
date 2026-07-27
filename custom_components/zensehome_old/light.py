from __future__ import annotations

import asyncio
from typing import Optional

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ZenseClient
from .const import (
    DOMAIN,
    DEFAULT_DEBOUNCE_S,
    DEFAULT_RECONCILE_DELAY_S,
    BRIGHTNESS_SCALE,
    SWITCH_NAME_KEYWORDS,
)
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
        self._reconcile_delay_s = float(DEFAULT_RECONCILE_DELAY_S)
        self._pending_task: Optional[asyncio.Task] = None
        self._pending_level: Optional[int] = None
        self._pending_old_level: Optional[int] = None
        self._pending_seq: Optional[int] = None

        # Monotonic per-entity command generation. This prevents old background
        # commands, rollbacks or delayed get_level reconciles from overwriting a
        # newer Home Assistant/Siri action when the user presses repeatedly.
        self._command_seq = 0

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

    def _next_command_seq(self) -> int:
        self._command_seq += 1
        return self._command_seq

    def _is_current_command(self, seq: int) -> bool:
        return seq == self._command_seq

    def _current_level(self) -> Optional[int]:
        return (self.coordinator.data or {}).get(self.dev.did)

    def _set_level_locally(self, raw_level: Optional[int]) -> None:
        data = dict(self.coordinator.data or {})
        if raw_level is None:
            data[self.dev.did] = None
        else:
            data[self.dev.did] = max(0, min(BRIGHTNESS_SCALE, int(raw_level)))
        self.coordinator.async_set_updated_data(data)

    async def _send_and_reconcile(
        self,
        seq: int,
        command: str,
        new_level: int,
        old_level: Optional[int],
    ) -> None:
        """Send the slow Zense command in the background and correct HA state afterwards.

        The seq guard makes the optimistic state safe for repeated presses:
        stale background tasks cannot roll back or reconcile over a newer command.
        """
        try:
            if command == "off" or new_level <= 0:
                ok = await self.client.set_off(self.dev.did)
            elif command == "on":
                ok = await self.client.set_on(self.dev.did)
            elif command == "fade":
                ok = await self.client.fade(self.dev.did, new_level)
            else:
                self.client.logger.warning("Unknown ZenseHome command %s for device %s", command, self.dev.did)
                return

            if not self._is_current_command(seq):
                return

            if not ok:
                self.client.logger.warning(
                    "ZenseHome command %s returned false for device %s; rolling back state",
                    command,
                    self.dev.did,
                )
                self._set_level_locally(old_level)
                return

            await asyncio.sleep(self._reconcile_delay_s)

            if not self._is_current_command(seq):
                return

            real_level = await self.client.get_level(self.dev.did)

            if not self._is_current_command(seq):
                return

            if real_level is not None:
                self._set_level_locally(real_level)

        except asyncio.CancelledError:
            return
        except Exception:
            self.client.logger.exception(
                "ZenseHome command/reconcile failed for device %s; rolling back state",
                self.dev.did,
            )
            if self._is_current_command(seq):
                self._set_level_locally(old_level)

    def _schedule_send_and_reconcile(
        self,
        seq: int,
        command: str,
        new_level: int,
        old_level: Optional[int],
    ) -> None:
        self.hass.async_create_task(self._send_and_reconcile(seq, command, new_level, old_level))

    async def async_turn_off(self, **kwargs) -> None:
        seq = self._next_command_seq()

        if self._pending_task:
            self._pending_task.cancel()
            self._pending_task = None
            self._pending_level = None
            self._pending_old_level = None
            self._pending_seq = None

        old_level = self._current_level()
        self._set_level_locally(0)
        self._schedule_send_and_reconcile(seq, "off", 0, old_level)

    async def async_turn_on(self, **kwargs) -> None:
        seq = self._next_command_seq()
        old_level = self._current_level()

        if ATTR_BRIGHTNESS not in kwargs:
            if self._pending_task:
                self._pending_task.cancel()
                self._pending_task = None
                self._pending_level = None
                self._pending_old_level = None
                self._pending_seq = None

            self._set_level_locally(BRIGHTNESS_SCALE)
            self._schedule_send_and_reconcile(seq, "on", BRIGHTNESS_SCALE, old_level)
            return

        raw = _ha_to_raw(int(kwargs[ATTR_BRIGHTNESS]))
        self._set_level_locally(raw)

        if self._pending_task is None or self._pending_task.done():
            self._pending_old_level = old_level
            self._pending_task = self.hass.async_create_task(self._debounced_send())

        self._pending_level = raw
        self._pending_seq = seq

    async def _debounced_send(self) -> None:
        try:
            await asyncio.sleep(self._debounce_s)
            lvl = self._pending_level
            old_level = self._pending_old_level
            seq = self._pending_seq
            self._pending_level = None
            self._pending_old_level = None
            self._pending_seq = None
            self._pending_task = None

            if lvl is None or seq is None:
                return

            if not self._is_current_command(seq):
                return

            command = "off" if lvl <= 0 else "fade"
            await self._send_and_reconcile(seq, command, lvl, old_level)

        except asyncio.CancelledError:
            return
        except Exception:
            self.client.logger.exception(
                "ZenseHome debounced dim command failed for device %s",
                self.dev.did,
            )
            seq = self._pending_seq
            if seq is not None and self._is_current_command(seq) and self._pending_old_level is not None:
                self._set_level_locally(self._pending_old_level)
            self._pending_level = None
            self._pending_old_level = None
            self._pending_seq = None
            self._pending_task = None
