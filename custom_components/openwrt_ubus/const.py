"""Costanti per l'integrazione OpenWrt Ubus."""

DOMAIN = "openwrt_ubus"
MANUFACTURER = "OpenWrt"

# Configurazione
CONF_HOSTNAME = "hostname"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_WIRELESS_BACKEND = "wireless_backend"
CONF_DHCP_BACKEND = "dhcp_backend"
CONF_MANAGED_SERVICES = "managed_services"

# Opzioni backend
WIRELESS_BACKENDS = ["hostapd", "iwinfo", "none"]
DHCP_BACKENDS = ["odhcpd", "dnsmasq", "none"]

# Timeout e intervalli
UPDATE_INTERVAL = 30
REQUEST_TIMEOUT = 10
KICK_BAN_DURATION = 60

# Servizi di sistema comuni
COMMON_SERVICES = [
    "network", "dnsmasq", "firewall", "dropbear", 
    "uhttpd", "odhcpd", "hostapd"
]