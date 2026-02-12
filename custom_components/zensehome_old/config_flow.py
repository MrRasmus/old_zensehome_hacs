from __future__ import annotations

import json
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_HOST, CONF_PORT, CONF_CODE,
    DEFAULT_PORT, DEFAULT_POLL_MIN,
    OPT_POLL_MIN, OPT_ENTITY_TYPES,
)

class ZenseHomeFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            schema = vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_CODE): int,
            })
            return self.async_show_form(step_id="user", data_schema=schema)

        await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"ZenseHome ({user_input[CONF_HOST]})",
            data=user_input,
            options={
                OPT_POLL_MIN: DEFAULT_POLL_MIN,
                OPT_ENTITY_TYPES: "{}",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZenseHomeOptionsFlow(config_entry)

class ZenseHomeOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        current_poll = int(self.entry.options.get(OPT_POLL_MIN, DEFAULT_POLL_MIN))
        current_types = self.entry.options.get(OPT_ENTITY_TYPES, "{}")
        try:
            json.loads(current_types or "{}")
        except Exception:
            current_types = "{}"

        if user_input is None:
            schema = vol.Schema({
                vol.Optional(OPT_POLL_MIN, default=current_poll): int,
                vol.Optional(
                    OPT_ENTITY_TYPES,
                    default=current_types,
                    description={"suggested_value": current_types},
                ): str,
            })
            return self.async_show_form(step_id="init", data_schema=schema)

        types_str = (user_input.get(OPT_ENTITY_TYPES) or "{}").strip()
        try:
            parsed = json.loads(types_str)
            if not isinstance(parsed, dict):
                types_str = "{}"
        except Exception:
            types_str = "{}"

        return self.async_create_entry(
            title="",
            data={
                OPT_POLL_MIN: int(user_input.get(OPT_POLL_MIN, current_poll)),
                OPT_ENTITY_TYPES: types_str,
            },
        )
