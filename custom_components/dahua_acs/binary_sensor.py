"""Binary sensor platform for Dahua ACS."""

from __future__ import annotations

import asyncio

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DahuaAcsCoordinator
from .entity import DahuaAcsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dahua ACS binary sensors."""
    coordinator: DahuaAcsCoordinator = hass.data[DOMAIN][entry.entry_id]
    doorbell = DahuaAcsDoorbellBinarySensor(hass, coordinator, entry.entry_id)
    async_add_entities([doorbell])


class DahuaAcsDoorbellBinarySensor(DahuaAcsEntity, BinarySensorEntity):
    """Momentary doorbell press from HTTP events."""

    _attr_translation_key = "doorbell"
    _attr_device_class = BinarySensorDeviceClass.DOORBELL
    _attr_icon = "mdi:doorbell"
    _attr_unique_id = "dahua_doorbell"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DahuaAcsCoordinator,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._entry_id = entry_id
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to doorbell events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._hass.bus.async_listen(
                f"{DOMAIN}_doorbell",
                self._handle_doorbell,
            )
        )

    @callback
    def _handle_doorbell(self, event) -> None:
        """Flash binary sensor on doorbell."""
        if event.data.get("device_id") != self._entry_id:
            return
        self._attr_is_on = True
        self.async_write_ha_state()
        self._hass.async_create_task(self._reset())

    async def _reset(self) -> None:
        """Turn off after a short pulse."""
        await asyncio.sleep(2)
        self._attr_is_on = False
        self.async_write_ha_state()
