"""Base entity for Dahua ACS integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import DahuaAcsCoordinator


class DahuaAcsEntity(CoordinatorEntity[DahuaAcsCoordinator]):
    """Base class for Dahua ACS entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DahuaAcsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{coordinator.api.host}/",
        )
