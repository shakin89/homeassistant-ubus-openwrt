"""Device tracker per OpenWrt Ubus."""
import logging
from typing import Dict, Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
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
    """Setup device tracker entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Crea device tracker per ogni dispositivo connesso
    if coordinator.data and "processed_devices" in coordinator.data:
        for mac, device_info in coordinator.data["processed_devices"].items():
            entities.append(OpenWrtDeviceTracker(coordinator, mac, device_info))
    
    async_add_entities(entities)

class OpenWrtDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Device tracker per dispositivi OpenWrt."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator, mac: str, device_info: Dict[str, Any]):
        """Initialize device tracker."""
        super().__init__(coordinator)
        self._mac = mac
        self._device_info = device_info
        
        # Entity info
        self._attr_unique_id = f"{DOMAIN}_{mac}"
        self._attr_name = device_info["full_display_name"]
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"device_{mac}")},
            "name": device_info["display_name"],
            "manufacturer": "Unknown",
            "model": "Network Device",
            "via_device": (DOMAIN, coordinator.hostname),
        }
    
    @property
    def source_type(self) -> SourceType:
        """Return source type."""
        return SourceType.ROUTER
    
    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        if not self.coordinator.data or "processed_devices" not in self.coordinator.data:
            return False
        
        device = self.coordinator.data["processed_devices"].get(self._mac)
        return device.get("connected", False) if device else False
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra attributes."""
        if not self.coordinator.data or "processed_devices" not in self.coordinator.data:
            return {}
        
        device = self.coordinator.data["processed_devices"].get(self._mac, {})
        
        attrs = {
            "mac_address": self._mac,
            "interface": device.get("interface"),
            "display_name": device.get("display_name"),
            "wireless": device.get("wireless", False),
        }
        
        # Aggiungi info wireless se disponibili
        if device.get("wireless"):
            if "signal" in device:
                attrs["signal_strength"] = device["signal"]
            if "rx_rate" in device:
                attrs["rx_rate"] = device["rx_rate"]
            if "tx_rate" in device:
                attrs["tx_rate"] = device["tx_rate"]
        
        return attrs