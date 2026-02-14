from __future__ import annotations

import json
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_CODE,
    DEFAULT_PORT,
    CONF_POLLING_MINUTES,
    CONF_ENTITY_TYPES_JSON,
    DEFAULT_POLLING_MINUTES,
)
from .api import ZenseClient


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            code = user_input[CONF_CODE]

            client = ZenseClient(host, port, code)
            ok = await client.async_test_connection(self.hass)

            if ok:
                await self.async_set_unique_id(f"{DOMAIN}_{host}_{port}_{code}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ZenseHome ({host})",
                    data=user_input,
                )

            errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_CODE): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}

        if user_input is not None:
            s = (user_input.get(CONF_ENTITY_TYPES_JSON) or "").strip()
            if s:
                try:
                    parsed = json.loads(s)
                    if not isinstance(parsed, dict):
                        raise ValueError
                    for v in parsed.values():
                        if str(v).lower().strip() not in ("light", "switch"):
                            raise ValueError
                except Exception:
                    errors["base"] = "invalid_json"
                else:
                    return self.async_create_entry(title="", data=user_input)
            else:
                return self.async_create_entry(title="", data=user_input)

        cur = self.config_entry.options

        poll_val = cur.get(CONF_POLLING_MINUTES, DEFAULT_POLLING_MINUTES)
        try:
            poll_default = int(poll_val)
        except Exception:
            poll_default = DEFAULT_POLLING_MINUTES

        ent_default = cur.get(CONF_ENTITY_TYPES_JSON, "")
        if ent_default is None:
            ent_default = ""
        ent_default = str(ent_default)

        schema = vol.Schema(
            {
                vol.Required(CONF_POLLING_MINUTES, default=poll_default): vol.Coerce(int),
                vol.Optional(CONF_ENTITY_TYPES_JSON, default=ent_default): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)