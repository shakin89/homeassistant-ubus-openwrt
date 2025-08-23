"""Button entities per OpenWrt Ubus."""
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenWrtDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup button entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Crea kick button per ogni dispositivo connesso  
    if coordinator.data and "processed_devices" in coordinator.data:
        for mac, device_info in coordinator.data["processed_devices"].items():
            entities.append(OpenWrtKickButton(coordinator, mac, device_info))
    
    async_add_entities(entities)

class OpenWrtKickButton(CoordinatorEntity, ButtonEntity):
    """Button per disconnettere dispositivo."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator, mac: str, device_info: dict):
        """Initialize kick button."""
        super().__init__(coordinator)
        self._mac = mac
        self._device_info = device_info
        
        # Entity info
        self._attr_unique_id = f"{DOMAIN}_kick_{mac}"
        self._attr_name = f"Kick {device_info['display_name']}"
        self._attr_icon = "mdi:wifi-off"
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"device_{mac}")},
            "name": device_info["display_name"],
            "manufacturer": "Unknown", 
            "model": "Network Device",
            "via_device": (DOMAIN, coordinator.hostname),
        }
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data or "processed_devices" not in self.coordinator.data:
            return False
        
        device = self.coordinator.data["processed_devices"].get(self._mac)
        return device.get("connected", False) if device else False
    
    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info(f"Kicking device {self._mac}")
        success = await self.coordinator.kick_device(self._mac)
        
        if not success:
            _LOGGER.error(f"Failed to kick device {self._mac}")