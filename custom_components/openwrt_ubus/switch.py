"""Switch entities per OpenWrt Ubus."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OpenWrtDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup switch entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Switch per ogni servizio gestito
    if coordinator.data and "services_status" in coordinator.data:
        for service_name in coordinator.managed_services:
            entities.append(OpenWrtServiceSwitch(coordinator, service_name))
    
    async_add_entities(entities)

class OpenWrtServiceSwitch(CoordinatorEntity, SwitchEntity):
    """Switch per controllare servizi sistema."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator, service_name: str):
        """Initialize service switch."""
        super().__init__(coordinator)
        self._service_name = service_name
        
        self._attr_unique_id = f"{DOMAIN}_service_{service_name}_{coordinator.hostname}"
        self._attr_name = f"{coordinator.hostname} {service_name.title()} Service"
        self._attr_icon = "mdi:cog"
        
        # Device info per router principale
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.hostname)},
            "name": f"OpenWrt - {coordinator.hostname}",
            "manufacturer": MANUFACTURER,
            "model": coordinator.data.get("system_info", {}).get("model", "Router") if coordinator.data else "Router",
            "sw_version": coordinator.data.get("system_info", {}).get("kernel", "Unknown") if coordinator.data else "Unknown",
        }
    
    @property
    def is_on(self) -> bool:
        """Return if service is running."""
        if not self.coordinator.data or "services_status" not in self.coordinator.data:
            return False
        
        service = self.coordinator.data["services_status"].get(self._service_name, {})
        return service.get("running", False)
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn service on."""
        await self.coordinator.control_service(self._service_name, "start")
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn service off."""
        await self.coordinator.control_service(self._service_name, "stop")
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return service attributes."""
        if not self.coordinator.data or "services_status" not in self.coordinator.data:
            return {}
        
        service = self.coordinator.data["services_status"].get(self._service_name, {})
        
        return {
            "service_name": self._service_name,
            "running": service.get("running", False),
        }