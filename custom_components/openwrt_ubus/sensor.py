"""Sensor entities per OpenWrt Ubus."""
import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import PERCENTAGE, UnitOfTime

from .const import DOMAIN, MANUFACTURER
from .coordinator import OpenWrtDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Sensori sistema router principale
    entities.extend([
        OpenWrtUptimeSensor(coordinator),
        OpenWrtCpuLoadSensor(coordinator, "1min"),
        OpenWrtCpuLoadSensor(coordinator, "5min"), 
        OpenWrtCpuLoadSensor(coordinator, "15min"),
        OpenWrtMemorySensor(coordinator, "total"),
        OpenWrtMemorySensor(coordinator, "free"),
        OpenWrtMemorySensor(coordinator, "available"),
    ])
    
    # Sensori per ogni interfaccia wireless
    if coordinator.data and "wireless_networks" in coordinator.data:
        for interface, network_info in coordinator.data["wireless_networks"].items():
            entities.extend([
                OpenWrtWirelessNetworkSensor(coordinator, interface, network_info),
                OpenWrtConnectedDevicesSensor(coordinator, interface),
            ])
    
    async_add_entities(entities)

class OpenWrtBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor per OpenWrt."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator):
        """Initialize base sensor."""
        super().__init__(coordinator)
        
        # Device info per router principale
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.hostname)},
            "name": f"OpenWrt - {coordinator.hostname}",
            "manufacturer": MANUFACTURER,
            "model": coordinator.data.get("system_info", {}).get("model", "Router") if coordinator.data else "Router",
            "sw_version": coordinator.data.get("system_info", {}).get("kernel", "Unknown") if coordinator.data else "Unknown",
        }

class OpenWrtUptimeSensor(OpenWrtBaseSensor):
    """Sensor per uptime sistema."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator):
        """Initialize uptime sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_uptime_{coordinator.hostname}"
        self._attr_name = f"{coordinator.hostname} Uptime"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:clock-outline"
    
    @property
    def native_value(self) -> int:
        """Return uptime in seconds."""
        if not self.coordinator.data or "system_info" not in self.coordinator.data:
            return 0
        return self.coordinator.data["system_info"].get("uptime", 0)

class OpenWrtCpuLoadSensor(OpenWrtBaseSensor):
    """Sensor per carico CPU."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator, period: str):
        """Initialize CPU load sensor."""
        super().__init__(coordinator)
        self._period = period
        self._attr_unique_id = f"{DOMAIN}_cpu_load_{period}_{coordinator.hostname}"
        self._attr_name = f"{coordinator.hostname} CPU Load {period}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cpu-64-bit"
    
    @property
    def native_value(self) -> float:
        """Return CPU load percentage."""
        if not self.coordinator.data or "system_info" not in self.coordinator.data:
            return 0
        return self.coordinator.data["system_info"].get(f"load_{self._period}", 0)

class OpenWrtMemorySensor(OpenWrtBaseSensor):
    """Sensor per memoria."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator, memory_type: str):
        """Initialize memory sensor."""
        super().__init__(coordinator)
        self._memory_type = memory_type
        self._attr_unique_id = f"{DOMAIN}_memory_{memory_type}_{coordinator.hostname}"
        self._attr_name = f"{coordinator.hostname} Memory {memory_type.title()}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:memory"
    
    @property
    def native_value(self) -> str:
        """Return memory info."""
        if not self.coordinator.data or "system_info" not in self.coordinator.data:
            return "0 KB"
        
        memory_info = self.coordinator.data["system_info"].get("memory", {})
        return memory_info.get(self._memory_type, "0 KB")

class OpenWrtWirelessNetworkSensor(CoordinatorEntity, SensorEntity):
    """Sensor per info rete wireless."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator, interface: str, network_info: dict):
        """Initialize wireless network sensor."""
        super().__init__(coordinator)
        self._interface = interface
        self._network_info = network_info
        
        self._attr_unique_id = f"{DOMAIN}_wireless_network_{interface}_{coordinator.hostname}"
        self._attr_name = f"{network_info.get('ssid', interface)} Network Info"
        self._attr_icon = "mdi:wifi-settings"
        
        # Device info per interfaccia wireless
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"wireless_{interface}")},
            "name": f"WiFi - {network_info.get('ssid', interface)}",
            "manufacturer": MANUFACTURER,
            "model": "Wireless Interface",
            "via_device": (DOMAIN, coordinator.hostname),
        }
    
    @property
    def native_value(self) -> str:
        """Return network status."""
        if not self.coordinator.data or "wireless_networks" not in self.coordinator.data:
            return "offline"
        
        network = self.coordinator.data["wireless_networks"].get(self._interface, {})
        return "online" if network.get("up", False) else "offline"
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return network attributes."""
        if not self.coordinator.data or "wireless_networks" not in self.coordinator.data:
            return {}
        
        network = self.coordinator.data["wireless_networks"].get(self._interface, {})
        
        return {
            "ssid": network.get("ssid", "N/A"),
            "interface": self._interface,
            "radio": network.get("radio", "N/A"),
            "channel": network.get("channel", "auto"),
            "encryption": network.get("encryption", "Open"),
            "tx_power": network.get("txpower", "auto"),
            "mode": network.get("mode", "ap"),
            "disabled": network.get("disabled", False),
        }

class OpenWrtConnectedDevicesSensor(CoordinatorEntity, SensorEntity):
    """Sensor per numero dispositivi connessi per interfaccia."""
    
    def __init__(self, coordinator: OpenWrtDataUpdateCoordinator, interface: str):
        """Initialize connected devices sensor."""
        super().__init__(coordinator)
        self._interface = interface
        
        self._attr_unique_id = f"{DOMAIN}_connected_devices_{interface}_{coordinator.hostname}"
        self._attr_name = f"{interface} Connected Devices"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:devices"
        
        # Device info per interfaccia wireless
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"wireless_{interface}")},
            "name": f"WiFi - {interface}",
            "manufacturer": MANUFACTURER,
            "model": "Wireless Interface", 
            "via_device": (DOMAIN, coordinator.hostname),
        }
    
    @property
    def native_value(self) -> int:
        """Return number of connected devices."""
        if not self.coordinator.data or "processed_devices" not in self.coordinator.data:
            return 0
        
        count = 0
        for device in self.coordinator.data["processed_devices"].values():
            if device.get("interface") == self._interface and device.get("connected", False):
                count += 1
        
        return count