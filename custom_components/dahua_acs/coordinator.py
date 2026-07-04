"""Data update coordinator for Dahua ACS."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DahuaAcsApi, DahuaAcsApiError, DahuaAcsConnectionError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DahuaAcsData:
    """Panel state."""

    door_status: str
    last_event: str = ""
    last_event_payload: dict[str, Any] = field(default_factory=dict)


class DahuaAcsCoordinator(DataUpdateCoordinator[DahuaAcsData]):
    """Poll Dahua access panel door status."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: DahuaAcsApi,
    ) -> None:
        self.api = api
        self.entry = entry
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

    async def _async_update_data(self) -> DahuaAcsData:
        previous = self.data
        try:
            door_status = await self.api.get_door_status()
        except DahuaAcsConnectionError as err:
            raise UpdateFailed(f"Unable to connect to Dahua panel: {err}") from err
        except DahuaAcsApiError as err:
            raise UpdateFailed(str(err)) from err

        return DahuaAcsData(
            door_status=door_status,
            last_event=previous.last_event if previous else "",
            last_event_payload=previous.last_event_payload if previous else {},
        )

    def handle_webhook_event(self, payload: dict[str, Any]) -> None:
        """Store last HTTP push event from the panel."""
        code = str(payload.get("Code", "unknown"))
        action = str(payload.get("Action", ""))
        event_data = payload.get("Data") or {}
        method = event_data.get("Method", "")
        summary = f"{code} {action}".strip()
        if event_data:
            summary = f"{summary} | method={method}"
        self.async_set_updated_data(
            DahuaAcsData(
                door_status=self.data.door_status if self.data else "unknown",
                last_event=summary[:255],
                last_event_payload=payload,
            )
        )

    async def async_open_door(self) -> None:
        """Open door and refresh status."""
        await self.api.open_door()
        await self.async_request_refresh()

    async def async_close_door(self) -> None:
        """Close door and refresh status."""
        await self.api.close_door()
        await self.async_request_refresh()
