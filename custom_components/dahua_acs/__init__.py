"""The Dahua ACS integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import DahuaAcsApi
from .const import (
    ACCESS_CONTROL_PRESS_ACTIONS,
    ALARM_LOCAL_PRESS_ACTIONS,
    CONF_CHANNEL,
    CONF_ENABLE_EVENTS,
    CONF_WEBHOOK_ID,
    DEFAULT_WEBHOOK_ID,
    DOORBELL_METHOD,
    DOMAIN,
)
from .coordinator import DahuaAcsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.LOCK, Platform.BINARY_SENSOR]


def _is_doorbell_press(payload: dict[str, Any]) -> bool:
    """True only on doorbell press, not release (AlarmLocal Stop)."""
    code = str(payload.get("Code", ""))
    action = str(payload.get("Action", ""))
    event_data = payload.get("Data") or {}
    method = event_data.get("Method")

    if code == "AlarmLocal":
        return action in ALARM_LOCAL_PRESS_ACTIONS
    if code == "AccessControl" and int(method or 0) == DOORBELL_METHOD:
        return action in ACCESS_CONTROL_PRESS_ACTIONS
    return False


async def _handle_webhook(
    hass: HomeAssistant,
    entry_id: str,
    request: web.Request,
) -> web.Response:
    """Handle EventHttpUpload POST from the panel."""
    coordinator: DahuaAcsCoordinator = hass.data[DOMAIN][entry_id]

    payload: dict[str, Any]
    content_type = request.headers.get("Content-Type", "")
    if "json" in content_type:
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            payload = {"raw": (await request.text())[:500]}
    else:
        text = await request.text()
        payload = {"raw": text[:500]}
        if text.strip().startswith("{"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                pass

    coordinator.handle_webhook_event(payload)

    if _is_doorbell_press(payload):
        event_data = payload.get("Data") or {}
        hass.bus.async_fire(
            f"{DOMAIN}_doorbell",
            {
                "device_id": entry_id,
                "code": str(payload.get("Code", "")),
                "method": event_data.get("Method"),
                "payload": payload,
            },
        )
    else:
        _LOGGER.debug(
            "Ignored doorbell trigger: code=%s action=%s",
            payload.get("Code"),
            payload.get("Action"),
        )

    return web.Response(status=200, text="OK")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dahua ACS from a config entry."""
    api = DahuaAcsApi(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_CHANNEL, 1),
    )
    coordinator = DahuaAcsCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    if entry.options.get(CONF_ENABLE_EVENTS, True):
        webhook_id = entry.data.get(CONF_WEBHOOK_ID, DEFAULT_WEBHOOK_ID)

        async def webhook_handler(
            _hass: HomeAssistant,
            _webhook_id: str,
            request: web.Request,
        ) -> web.Response:
            return await _handle_webhook(hass, entry.entry_id, request)

        webhook.async_register(
            hass,
            DOMAIN,
            entry.title,
            webhook_id,
            webhook_handler,
            allowed_methods=("POST",),
            local_only=True,
        )
        entry.async_on_unload(
            lambda: webhook.async_unregister(hass, webhook_id)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if entry.data.get("area_id"):
        device_registry = dr.async_get(hass)
        if device := device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        ):
            device_registry.async_update_device(
                device.id, area_id=entry.data["area_id"]
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
