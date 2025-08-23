"""Config flow per OpenWrt Ubus."""
import asyncio
import logging
import voluptuous as vol
from typing import Any, Dict, Optional
import requests
import json

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN, CONF_HOSTNAME, CONF_WIRELESS_BACKEND, 
    CONF_DHCP_BACKEND, CONF_MANAGED_SERVICES,
    WIRELESS_BACKENDS, DHCP_BACKENDS, COMMON_SERVICES
)

_LOGGER = logging.getLogger(__name__)

class OpenWrtUbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow per OpenWrt Ubus."""
    
    VERSION = 1
    
    def __init__(self):
        """Initialize the config flow."""
        self.data = {}
        self.available_services = []
    
    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            # Test connessione e recupera servizi
            try:
                services = await self._test_connection(user_input)
                if services:
                    self.data.update(user_input)
                    self.available_services = services
                    return await self.async_step_services()
                else:
                    errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Unexpected exception: %s", e)
                errors["base"] = "unknown"
        
        data_schema = vol.Schema({
            vol.Required(CONF_HOSTNAME): str,
            vol.Required(CONF_USERNAME, default="root"): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_WIRELESS_BACKEND, default="hostapd"): vol.In(WIRELESS_BACKENDS),
            vol.Required(CONF_DHCP_BACKEND, default="dnsmasq"): vol.In(DHCP_BACKENDS),
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
    
    async def async_step_services(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle services selection."""
        if user_input is not None:
            self.data[CONF_MANAGED_SERVICES] = user_input[CONF_MANAGED_SERVICES]
            
            # Create entry
            await self.async_set_unique_id(self.data[CONF_HOSTNAME])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"OpenWrt - {self.data[CONF_HOSTNAME]}",
                data=self.data
            )
        
        # Prepara lista servizi disponibili
        services_options = {service: service for service in self.available_services}
        
        data_schema = vol.Schema({
            vol.Required(CONF_MANAGED_SERVICES, default=list(self.available_services)): cv.multi_select(services_options)
        })
        
        return self.async_show_form(
            step_id="services",
            data_schema=data_schema
        )
    
    async def _test_connection(self, config: Dict[str, Any]) -> list:
        """Test connessione e recupera servizi disponibili."""
        try:
            hostname = config[CONF_HOSTNAME]
            username = config[CONF_USERNAME]  
            password = config[CONF_PASSWORD]
            
            # Test connessione ubus
            session_id = await self._get_ubus_session(hostname, username, password)
            if not session_id:
                return []
            
            # Recupera lista servizi
            services = await self._get_system_services(hostname, session_id)
            return services
            
        except Exception as e:
            _LOGGER.error(f"Test connessione fallito: {e}")
            return []
    
    async def _get_ubus_session(self, hostname: str, username: str, password: str) -> Optional[str]:
        """Ottieni session ID ubus."""
        url = f"http://{hostname}/ubus"
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [
                "00000000000000000000000000000000",
                "session",
                "login",
                {"username": username, "password": password}
            ]
        }
        
        try:
            response = await self.hass.async_add_executor_job(
                lambda: requests.post(url, data=json.dumps(payload), 
                                     headers={'Content-Type': 'application/json'}, 
                                     timeout=10)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("result") and len(result["result"]) > 1:
                    return result["result"][1].get("ubus_rpc_session")
        except Exception as e:
            _LOGGER.error(f"Errore login ubus: {e}")
        
        return None
    
    async def _get_system_services(self, hostname: str, session_id: str) -> list:
        """Recupera lista servizi sistema."""
        url = f"http://{hostname}/ubus"
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [session_id, "service", "list", {}]
        }
        
        try:
            response = await self.hass.async_add_executor_job(
                lambda: requests.post(url, data=json.dumps(payload), 
                                     headers={'Content-Type': 'application/json'}, 
                                     timeout=10)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("result") and len(result["result"]) > 1:
                    services_data = result["result"][1]
                    return list(services_data.keys()) if services_data else COMMON_SERVICES
        except Exception as e:
            _LOGGER.error(f"Errore recupero servizi: {e}")
        
        return COMMON_SERVICES