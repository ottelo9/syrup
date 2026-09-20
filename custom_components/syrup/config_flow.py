"""Einrichtungsdialog der SYRUP-Integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_POLL_INTERVAL,
    CONF_RELAY_URL,
    CONF_SERIAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RELAY_URL,
    DOMAIN,
)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            int, vol.Range(min=5, max=600)
        ),
        vol.Optional(CONF_RELAY_URL, default=DEFAULT_RELAY_URL): str,
    }
)


class SyrupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fragt ab, welches Gerät eingebunden werden soll."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=SCHEMA)

        serial = user_input[CONF_SERIAL].strip().upper()
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"SYR {serial}", data={**user_input, CONF_SERIAL: serial}
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return SyrupOptionsFlow()


class SyrupOptionsFlow(OptionsFlow):
    """Taktrate und Weiterleitung nachträglich ändern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(int, vol.Range(min=5, max=600)),
                vol.Optional(
                    CONF_RELAY_URL, default=current.get(CONF_RELAY_URL, DEFAULT_RELAY_URL)
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
