"""Sensor platform for Dahua ACS."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DahuaAcsCoordinator
from .entity import DahuaAcsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dahua ACS sensors."""
    coordinator: DahuaAcsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DahuaAcsDoorStatusSensor(coordinator),
            DahuaAcsLastEventSensor(coordinator),
        ]
    )


class DahuaAcsDoorStatusSensor(DahuaAcsEntity, SensorEntity):
    """Door status reported by the panel."""

    _attr_has_entity_name = False
    _attr_name = "Dahua Door Status"
    _attr_icon = "mdi:door"
    _attr_unique_id = "dahua_door_status"

    @property
    def native_value(self) -> str:
        """Return door status."""
        return self.coordinator.data.door_status


class DahuaAcsLastEventSensor(DahuaAcsEntity, SensorEntity):
    """Last HTTP push event from the panel."""

    _attr_has_entity_name = False
    _attr_name = "Dahua — последнее HTTP-событие"
    _attr_icon = "mdi:doorbell"
    _attr_unique_id = "dahua_last_http_event"

    @property
    def native_value(self) -> str | None:
        """Return last event summary."""
        return self.coordinator.data.last_event or None

    @property
    def extra_state_attributes(self) -> dict:
        """Return raw event payload."""
        payload = self.coordinator.data.last_event_payload
        if not payload:
            return {}
        return {"payload": payload}
