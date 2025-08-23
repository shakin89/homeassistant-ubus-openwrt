"""Data Update Coordinator per OpenWrt Ubus."""
import asyncio
import logging
from datetime import timedelta, datetime
from typing import Any, Dict, List, Optional
import requests
import json
import re

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from .const import (
    DOMAIN, UPDATE_INTERVAL, REQUEST_TIMEOUT,
    CONF_HOSTNAME, CONF_WIRELESS_BACKEND, CONF_DHCP_BACKEND,
    CONF_MANAGED_SERVICES, KICK_BAN_DURATION
)

_LOGGER = logging.getLogger(__name__)

class OpenWrtDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator per gestire aggiornamenti dati OpenWrt."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize coordinator."""
        self.hass = hass
        self.entry = entry
        self.hostname = entry.data[CONF_HOSTNAME]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.wireless_backend = entry.data[CONF_WIRELESS_BACKEND]
        self.dhcp_backend = entry.data[CONF_DHCP_BACKEND]
        self.managed_services = entry.data[CONF_MANAGED_SERVICES]
        
        self.session_id = None
        self.kicked_devices = {}  # MAC -> timestamp
        self.ethers_map = {}  # MAC -> nome da /etc/ethers
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL)
        )
    
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data da OpenWrt."""
        try:
            # Ensure session
            if not self.session_id:
                self.session_id = await self._get_session()
                if not self.session_id:
                    raise UpdateFailed("Non posso ottenere session ubus")
            
            # Fetch all data
            data = {
                "system_info": await self._get_system_info(),
                "wireless_info": await self._get_wireless_info(),
                "connected_devices": await self._get_connected_devices(),
                "dhcp_leases": await self._get_dhcp_leases(),
                "services_status": await self._get_services_status(),
                "wireless_networks": await self._get_wireless_networks(),
            }
            
            # Process device names
            await self._load_ethers_map()
            data["processed_devices"] = self._process_device_names(
                data["connected_devices"], 
                data["dhcp_leases"]
            )
            
            return data
            
        except Exception as e:
            _LOGGER.error(f"Errore aggiornamento dati: {e}")
            # Resetiamo session in caso di errore
            self.session_id = None
            raise UpdateFailed(f"Errore comunicazione OpenWrt: {e}")
    
    async def _ubus_call(self, object_name: str, method: str, params: dict = None) -> Any:
        """Esegui chiamata ubus."""
        if not self.session_id:
            self.session_id = await self._get_session()
            if not self.session_id:
                raise Exception("Session ubus non disponibile")
        
        url = f"http://{self.hostname}/ubus"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [self.session_id, object_name, method, params or {}]
        }
        
        try:
            response = await self.hass.async_add_executor_job(
                requests.post, url, json.dumps(payload), REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("result") and len(result["result"]) > 1:
                    return result["result"][1]
                elif result.get("error"):
                    raise Exception(f"Errore ubus: {result['error']}")
            else:
                raise Exception(f"HTTP error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Errore richiesta: {e}")
        
        return None
    
    async def _get_session(self) -> Optional[str]:
        """Ottieni session ID."""
        url = f"http://{self.hostname}/ubus"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [
                "00000000000000000000000000000000",
                "session",
                "login",
                {"username": self.username, "password": self.password}
            ]
        }
        
        try:
            response = await self.hass.async_add_executor_job(
                requests.post, url, json.dumps(payload), REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("result") and len(result["result"]) > 1:
                    return result["result"][1].get("ubus_rpc_session")
        except Exception as e:
            _LOGGER.error(f"Errore login: {e}")
        
        return None
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Ottieni info sistema."""
        try:
            board_info = await self._ubus_call("system", "board") or {}
            system_info = await self._ubus_call("system", "info") or {}
            
            # Calcola percentuali CPU load
            load_info = system_info.get("load", [0, 0, 0])
            cpu_cores = 1  # Assumiamo 1 core se non specificato
            
            return {
                "hostname": board_info.get("hostname", "OpenWrt"),
                "model": board_info.get("model", "Unknown"),
                "kernel": board_info.get("kernel", "Unknown"),
                "uptime": system_info.get("uptime", 0),
                "load_1min": round((load_info[0] / cpu_cores) * 100, 1) if load_info[0] else 0,
                "load_5min": round((load_info[1] / cpu_cores) * 100, 1) if load_info[1] else 0,
                "load_15min": round((load_info[2] / cpu_cores) * 100, 1) if load_info[2] else 0,
                "memory": self._format_memory(system_info.get("memory", {})),
            }
        except Exception as e:
            _LOGGER.error(f"Errore system info: {e}")
            return {}
    
    def _format_memory(self, memory_info: Dict) -> Dict[str, str]:
        """Format memory info in human readable format."""
        if not memory_info:
            return {}
        
        def format_bytes(bytes_val):
            if bytes_val > 1024**3:
                return f"{bytes_val / 1024**3:.1f} GB"
            elif bytes_val > 1024**2:
                return f"{bytes_val / 1024**2:.1f} MB"
            else:
                return f"{bytes_val / 1024:.1f} KB"
        
        return {
            "total": format_bytes(memory_info.get("total", 0)),
            "free": format_bytes(memory_info.get("free", 0)),
            "available": format_bytes(memory_info.get("available", 0)),
        }
    
    async def _get_wireless_info(self) -> Dict[str, Any]:
        """Ottieni info wireless."""
        if self.wireless_backend == "none":
            return {}
        
        try:
            if self.wireless_backend == "hostapd":
                return await self._get_hostapd_info()
            elif self.wireless_backend == "iwinfo":
                return await self._get_iwinfo()
        except Exception as e:
            _LOGGER.error(f"Errore wireless info: {e}")
        
        return {}
    
    async def _get_hostapd_info(self) -> Dict[str, Any]:
        """Ottieni info da hostapd."""
        try:
            interfaces = await self._ubus_call("hostapd", "get_clients") or {}
            wireless_info = {}
            
            for iface, data in interfaces.items():
                clients = data.get("clients", {})
                wireless_info[iface] = {
                    "interface": iface,
                    "clients": clients,
                    "client_count": len(clients)
                }
            
            return wireless_info
        except Exception as e:
            _LOGGER.error(f"Errore hostapd: {e}")
            return {}
    
    async def _get_iwinfo(self) -> Dict[str, Any]:
        """Ottieni info da iwinfo."""
        try:
            # Implementazione iwinfo
            return {}
        except Exception as e:
            _LOGGER.error(f"Errore iwinfo: {e}")
            return {}
    
    async def _get_connected_devices(self) -> Dict[str, Any]:
        """Ottieni dispositivi connessi."""
        devices = {}
        
        # Da wireless
        wireless_info = await self._get_wireless_info()
        for iface, data in wireless_info.items():
            for mac, client_info in data.get("clients", {}).items():
                devices[mac] = {
                    "mac": mac,
                    "interface": iface,
                    "connected": True,
                    "wireless": True,
                    **client_info
                }
        
        return devices
    
    async def _get_dhcp_leases(self) -> Dict[str, Any]:
        """Ottieni DHCP leases."""
        if self.dhcp_backend == "none":
            return {}
        
        try:
            if self.dhcp_backend == "dnsmasq":
                return await self._get_dnsmasq_leases()
            elif self.dhcp_backend == "odhcpd":
                return await self._get_odhcpd_leases()
        except Exception as e:
            _LOGGER.error(f"Errore DHCP leases: {e}")
        
        return {}
    
    async def _get_dnsmasq_leases(self) -> Dict[str, Any]:
        """Ottieni lease dnsmasq."""
        try:
            # Leggi file leases dnsmasq
            leases = await self._ubus_call("file", "read", {"path": "/var/lib/dhcp/dhcpd.leases"})
            # Parse leases file - implementazione semplificata
            return {}
        except Exception:
            return {}
    
    async def _get_odhcpd_leases(self) -> Dict[str, Any]:
        """Ottieni lease odhcpd."""
        try:
            # Implementazione odhcpd
            return {}
        except Exception:
            return {}
    
    async def _get_services_status(self) -> Dict[str, Any]:
        """Ottieni stato servizi."""
        try:
            services = await self._ubus_call("service", "list") or {}
            status = {}
            
            for service_name in self.managed_services:
                if service_name in services:
                    service_data = services[service_name]
                    # Determina se il servizio è running
                    is_running = bool(service_data.get("instances", {}).get("instance1", {}).get("pid"))
                    status[service_name] = {
                        "name": service_name,
                        "running": is_running,
                        "data": service_data
                    }
            
            return status
        except Exception as e:
            _LOGGER.error(f"Errore services status: {e}")
            return {}
    
    async def _get_wireless_networks(self) -> Dict[str, Any]:
        """Ottieni info reti wireless."""
        try:
            # Ottieni info interfacce wireless
            network_status = await self._ubus_call("network.wireless", "status") or {}
            networks = {}
            
            for radio, radio_data in network_status.items():
                for iface_name, iface_data in radio_data.get("interfaces", {}).items():
                    config = iface_data.get("config", {})
                    ifname = iface_data.get("ifname", iface_name)
                    
                    networks[ifname] = {
                        "interface": ifname,
                        "radio": radio,
                        "ssid": config.get("ssid", "N/A"),
                        "mode": config.get("mode", "ap"),
                        "encryption": self._format_encryption(config.get("encryption", {})),
                        "channel": radio_data.get("config", {}).get("channel", "auto"),
                        "txpower": radio_data.get("config", {}).get("txpower", "auto"),
                        "disabled": config.get("disabled", False),
                        "up": iface_data.get("up", False),
                    }
            
            return networks
        except Exception as e:
            _LOGGER.error(f"Errore wireless networks: {e}")
            return {}
    
    def _format_encryption(self, encryption: Dict) -> str:
        """Formatta info crittografia."""
        if not encryption:
            return "Open"
        
        enabled = encryption.get("enabled", False)
        if not enabled:
            return "Open"
        
        auth = encryption.get("auth_suites", [])
        cipher = encryption.get("pair_ciphers", [])
        
        if "psk" in auth and "ccmp" in cipher:
            return "WPA2-PSK (CCMP)"
        elif "psk" in auth:
            return "WPA-PSK"
        elif auth and cipher:
            return f"{'/'.join(auth).upper()} ({'/'.join(cipher).upper()})"
        else:
            return "Encrypted"
    
    async def _load_ethers_map(self):
        """Carica mappatura MAC->nome da /etc/ethers."""
        try:
            ethers_content = await self._ubus_call("file", "read", {"path": "/etc/ethers"})
            if ethers_content and ethers_content.get("data"):
                content = ethers_content["data"]
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2:
                            mac = parts[0].lower()
                            name = ' '.join(parts[1:])
                            self.ethers_map[mac] = name
        except Exception as e:
            _LOGGER.debug(f"Non posso leggere /etc/ethers: {e}")
    
    def _process_device_names(self, devices: Dict, dhcp_leases: Dict) -> Dict[str, Any]:
        """Processa nomi dispositivi con priorità ethers -> DHCP -> MAC."""
        processed = {}
        
        for mac, device_info in devices.items():
            mac_lower = mac.lower()
            
            # Priorità nomi: ethers -> DHCP hostname -> MAC
            display_name = mac
            if mac_lower in self.ethers_map:
                display_name = self.ethers_map[mac_lower]
            elif mac in dhcp_leases and dhcp_leases[mac].get("hostname"):
                display_name = dhcp_leases[mac]["hostname"]
            
            # Aggiungi interfaccia al nome se disponibile
            interface = device_info.get("interface", "unknown")
            full_name = f"{display_name} ({interface})"
            
            processed[mac] = {
                **device_info,
                "display_name": display_name,
                "full_display_name": full_name,
                "entity_id": f"{DOMAIN}.{self._slugify(full_name)}",
            }
        
        return processed
    
    def _slugify(self, text: str) -> str:
        """Convert text to valid entity ID."""
        # Rimuovi caratteri speciali e sostituisci con underscore
        text = re.sub(r'[^a-zA-Z0-9_]', '_', text.lower())
        # Rimuovi underscore multipli
        text = re.sub(r'_+', '_', text)
        # Rimuovi underscore iniziali/finali
        return text.strip('_')
    
    async def kick_device(self, mac: str, interface: str = None) -> bool:
        """Disconnetti dispositivo."""
        try:
            if self.wireless_backend == "hostapd":
                # Se interface specificata, disconnetti solo da quella
                if interface:
                    result = await self._ubus_call("hostapd", "del_client", {
                        "addr": mac,
                        "interface": interface,
                        "deauth": True,
                        "reason": 5,  # BSS terminating
                        "ban_time": KICK_BAN_DURATION * 1000  # ms
                    })
                else:
                    # Disconnetti da tutte le interfacce
                    wireless_info = self.data.get("wireless_info", {})
                    for iface in wireless_info.keys():
                        await self._ubus_call("hostapd", "del_client", {
                            "addr": mac,
                            "interface": iface, 
                            "deauth": True,
                            "reason": 5,
                            "ban_time": KICK_BAN_DURATION * 1000
                        })
                
                # Traccia dispositivo kickato
                self.kicked_devices[mac] = datetime.now()
                
                # Forza aggiornamento dopo kick
                await self.async_request_refresh()
                
                return True
                
        except Exception as e:
            _LOGGER.error(f"Errore kick dispositivo {mac}: {e}")
        
        return False
    
    async def control_service(self, service_name: str, action: str) -> bool:
        """Controlla servizio (start/stop/restart)."""
        if service_name not in self.managed_services:
            _LOGGER.error(f"Servizio {service_name} non gestito")
            return False
        
        try:
            if action == "restart":
                await self._ubus_call("service", "restart", {"name": service_name})
            elif action == "start": 
                await self._ubus_call("service", "start", {"name": service_name})
            elif action == "stop":
                await self._ubus_call("service", "stop", {"name": service_name})
            else:
                _LOGGER.error(f"Azione {action} non supportata")
                return False
            
            # Forza aggiornamento dopo controllo servizio
            await asyncio.sleep(2)  # Aspetta che il servizio si avvii/fermi
            await self.async_request_refresh()
            
            return True
            
        except Exception as e:
            _LOGGER.error(f"Errore controllo servizio {service_name} {action}: {e}")
            return False