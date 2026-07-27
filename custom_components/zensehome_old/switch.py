from __future__ import annotations

import asyncio
from typing import Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ZenseClient
from .const import DOMAIN, SWITCH_NAME_KEYWORDS, BRIGHTNESS_SCALE, DEFAULT_RECONCILE_DELAY_S
from .coordinator import ZenseCoordinator, ZenseDevice


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
            ents.append(ZenseSwitch(entry, client, coordinator, dev))

    async_add_entities(ents)


class ZenseSwitch(CoordinatorEntity[ZenseCoordinator], SwitchEntity):
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
        self._reconcile_delay_s = float(DEFAULT_RECONCILE_DELAY_S)

        # Monotonic per-entity command generation. This prevents old background
        # commands, rollbacks or delayed get_level reconciles from overwriting a
        # newer Home Assistant/Siri action when the user presses repeatedly.
        self._command_seq = 0

        self._attr_name = f"{dev.name} (Zense)"
        self._attr_unique_id = f"{entry.entry_id}_{dev.did}_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZenseHome",
            "manufacturer": "Zense",
            "model": "TCP Controller",
        }

    @property
    def is_on(self) -> bool:
        lvl = (self.coordinator.data or {}).get(self.dev.did)
        return bool(lvl and lvl > 0)

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
            else:
                ok = await self.client.set_on(self.dev.did)

            if not self._is_current_command(seq):
                return

            if not ok:
                self.client.logger.warning(
                    "ZenseHome switch command %s returned false for device %s; rolling back state",
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
                "ZenseHome switch command/reconcile failed for device %s; rolling back state",
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
        old_level = self._current_level()
        self._set_level_locally(0)
        self._schedule_send_and_reconcile(seq, "off", 0, old_level)

    async def async_turn_on(self, **kwargs) -> None:
        seq = self._next_command_seq()
        old_level = self._current_level()
        self._set_level_locally(BRIGHTNESS_SCALE)
        self._schedule_send_and_reconcile(seq, "on", BRIGHTNESS_SCALE, old_level)
