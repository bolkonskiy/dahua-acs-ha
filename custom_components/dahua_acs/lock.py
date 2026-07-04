"""Lock platform for Dahua ACS."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
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
    """Set up Dahua ACS lock."""
    coordinator: DahuaAcsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DahuaAcsDoorLock(coordinator)])


class DahuaAcsDoorLock(DahuaAcsEntity, LockEntity):
    """Remote open/close for the gate."""

    _attr_translation_key = "door"
    _attr_icon = "mdi:door-sliding-lock"
    _attr_unique_id = "dahua_door"

    @property
    def is_jammed(self) -> bool:
        """Return True if door status is Break."""
        return self.coordinator.data.door_status == "Break"

    @property
    def is_locked(self) -> bool:
        """Return True when door is closed."""
        return self.coordinator.data.door_status != "Open"

    @property
    def is_unlocked(self) -> bool:
        """Return True when door is open."""
        return self.coordinator.data.door_status == "Open"

    async def async_unlock(self, **kwargs) -> None:
        """Open the gate."""
        await self.coordinator.async_open_door()

    async def async_lock(self, **kwargs) -> None:
        """Close the gate."""
        await self.coordinator.async_close_door()
