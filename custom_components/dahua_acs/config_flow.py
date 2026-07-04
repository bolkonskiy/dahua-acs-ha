"""Config flow for Dahua ACS integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .api import DahuaAcsApi, DahuaAcsApiError, DahuaAcsConnectionError
from .const import (
    CONF_CHANNEL,
    CONF_ENABLE_EVENTS,
    CONF_SCAN_INTERVAL,
    CONF_WEBHOOK_ID,
    DEFAULT_CHANNEL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DEFAULT_WEBHOOK_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CHANNEL, default=DEFAULT_CHANNEL): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=4)
        ),
    }
)


async def validate_panel(
    host: str, username: str, password: str, channel: int
) -> str:
    """Validate panel connectivity and return entry title."""
    api = DahuaAcsApi(host, username, password, channel)
    await api.get_door_status()
    return f"Dahua ({api.host})"


class DahuaAcsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dahua ACS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            channel = user_input.get(CONF_CHANNEL, DEFAULT_CHANNEL)

            unique_id = f"{host.lower()}:{channel}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                title = await validate_panel(host, username, password, channel)
            except DahuaAcsConnectionError:
                errors["base"] = "cannot_connect"
            except DahuaAcsApiError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Dahua ACS setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: DahuaAcsApi(host, username, password, channel).host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_CHANNEL: channel,
                        CONF_WEBHOOK_ID: DEFAULT_WEBHOOK_ID,
                    },
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_ENABLE_EVENTS: True,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow handler."""
        return DahuaAcsOptionsFlow(config_entry)


class DahuaAcsOptionsFlow(OptionsFlow):
    """Handle Dahua ACS options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Dahua ACS options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Optional(
                    CONF_ENABLE_EVENTS,
                    default=options.get(CONF_ENABLE_EVENTS, True),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
