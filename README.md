# 📡 OpenWrt Ubus Integration for Home Assistant

[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

Una integrazione HACS avanzata che trasforma router OpenWrt in hub smart home completi, fornendo monitoraggio dispositivi, controllo sistema e gestione rete in tempo reale.

![OpenWrt Integration](https://img.shields.io/badge/OpenWrt-Integration-blue?style=for-the-badge&logo=openwrt)

## ✨ Caratteristiche Principali

### 🏷️ Device Tracking Intelligente
- **Nomi leggibili**: Dispositivi mostrati come `iphonefabrizio (WifiCasa)` invece di indirizzi MAC
- **Roaming unificato**: Stesso dispositivo = stessa entità anche cambiando Access Point
- **Risoluzione nomi**: Priorità `/etc/ethers` → hostname DHCP → MAC address
- **Tracciamento real-time**: Aggiornamenti istantanei su connessione/disconnessione

### 🎛️ Controllo Dispositivi WiFi
- **Kick buttons**: Disconnetti dispositivi con nomi leggibili (`Kick iphonefabrizio`)
- **Disconnessione unificata**: Un pulsante disconnette da tutti gli AP contemporaneamente
- **Ban temporaneo**: Impedisce riconnessione per 60 secondi post-kick
- **Gestione multi-AP**: Supporto reti mesh e access point multipli

### 📊 Monitoraggio Sistema OpenWrt
- **Metriche sistema**: Uptime, carico CPU (1/5/15 min) espresso in percentuale, memoria (totale/libera/disponibile)
- **Stato interfacce wireless**: SSID, canale, crittografia, dispositivi connessi
- **Gestione servizi**: Start/stop/restart servizi sistema (dnsmasq, firewall, network, etc.)

### 📡 Info Reti Wireless Dettagliate
- Elenco completo reti wireless con parametri leggibili
- Canale, potenza TX, crittografia, modalità
- Conteggio dispositivi connessi per interfaccia

### 🏗️ Architettura Gerarchica
- **Router principale**: Device principale con tutti gli AP come sub-device
- **AP come dispositivi**: Ogni interfaccia wireless come device separato
- **Device STA**: Dispositivi connessi sotto rispettivo AP

## 🚀 Installazione

### Via HACS (Consigliato)

1. Apri HACS in Home Assistant
2. Vai su "Integrazioni"
3. Clicca sui tre puntini in alto a destra → "Repository personalizzati"
4. Aggiungi questo URL: `https://github.com/shakin89/homeassistant-ubus-openwrt`
5. Seleziona categoria "Integration"
6. Clicca "Aggiungi"
7. Installa "OpenWrt Ubus Integration"
8. Riavvia Home Assistant

### Installazione Manuale

1. Scarica la cartella `custom_components/openwrt_ubus`
2. Copiala in `<config_dir>/custom_components/openwrt_ubus`
3. Riavvia Home Assistant

## ⚙️ Configurazione

### Setup Router OpenWrt

1. **Abilita ubus HTTP**: Assicurati che ubus sia accessibile via HTTP
```bash
uci set uhttpd.main.ubus_prefix='/ubus'
uci commit uhttpd
/etc/init.d/uhttpd restart
```

2. **Configura /etc/ethers** (opzionale ma consigliato):
```bash
# /etc/ethers - Mapping MAC -> Nome leggibile
aa:bb:cc:dd:ee:ff    iPhoneFabrizio
11:22:33:44:55:66    LaptopSara
```

### Setup Home Assistant

1. Vai su **Impostazioni** → **Dispositivi e Servizi** → **Aggiungi Integrazione**
2. Cerca "OpenWrt Ubus"
3. Inserisci i dati richiesti:
   - **Hostname/IP**: Indirizzo del router (es. `192.168.1.1` o `router.local`)
   - **Username**: Solitamente `root`
   - **Password**: Password del router
   - **Backend Wireless**: `hostapd` (consigliato), `iwinfo`, o `none`
   - **Backend DHCP**: `dnsmasq` (consigliato), `odhcpd`, o `none`
4. Seleziona i servizi da gestire dalla lista disponibile

## 📱 Entità Create

### Device Tracker
- `device_tracker.iphonefabrizio_wificasa` - Tracciamento dispositivi con nomi leggibili

### Sensori Sistema
- `sensor.openwrt_uptime` - Uptime del router
- `sensor.openwrt_cpu_load_1min` - Carico CPU 1 minuto (%)
- `sensor.openwrt_memory_total` - Memoria totale
- `sensor.openwrt_wlan0_connected_devices` - Dispositivi connessi per AP

### Pulsanti
- `button.kick_iphonefabrizio` - Disconnetti dispositivo specifico

### Switch Servizi
- `switch.openwrt_dnsmasq_service` - Controlla servizio dnsmasq
- `switch.openwrt_firewall_service` - Controlla firewall

## 🔧 Automazioni Esempio

### Kick Dispositivo Sconosciuto
```yaml
automation:
  - alias: "Kick Unknown Devices"
    trigger:
      - platform: state
        entity_id: device_tracker.unknown_device
        to: 'home'
    action:
      - service: button.press
        target:
          entity_id: button.kick_unknown_device
```

### Notifica Nuovo Dispositivo
```yaml
automation:
  - alias: "New Device Connected"
    trigger:
      - platform: state
        entity_id: device_tracker.*
        to: 'home'
    action:
      - service: notify.mobile_app
        data:
          message: "Nuovo dispositivo connesso: {{ trigger.to_state.name }}"
```

### Riavvio Automatico Servizi
```yaml
automation:
  - alias: "Restart Network Service Daily"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: openwrt_ubus.restart_service
        data:
          service_name: "network"
```

## 🐛 Troubleshooting

### Connessione Fallisce
- Verifica che ubus sia abilitato: `uci show uhttpd | grep ubus`
- Controlla firewall: porta 80 deve essere accessibile
- Test manuale: `curl http://ROUTER_IP/ubus`

### Device Non Riconosciuti
- Aggiungi mapping in `/etc/ethers`
- Verifica backend DHCP configurato correttamente
- Controlla log HA: `Settings` → `System` → `Logs`

### Servizi Non Controllabili
- Verifica che il servizio sia nella lista gestiti
- Controlla permessi utente per controllo servizi

## 🤝 Contribuire

Contributi benvenuti! Per favore:

1. Fork del repository
2. Crea feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit modifiche (`git commit -m 'Add amazing feature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Apri Pull Request

## 📋 TODO

- [ ] Supporto IPv6
- [ ] Integrazione con OpenWrt LuCI
- [ ] Gestione VLAN
- [ ] Statistiche traffico per dispositivo
- [ ] Controllo QoS
- [ ] Backup/restore configurazioni

## 📄 Licenza

Distribuito sotto licenza MIT. Vedi `LICENSE` per maggiori informazioni.

## 🙏 Ringraziamenti

- [Home Assistant](https://www.home-assistant.io/)
- [HACS](https://hacs.xyz/)
- [OpenWrt Project](https://openwrt.org/)

---

⭐ **Se questo progetto ti è utile, lascia una stella!** ⭐

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/shakin89/homeassistant-ubus-openwrt.svg?style=for-the-badge
[releases]: https://github.com/shakin89/homeassistant-ubus-openwrt/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/shakin89/homeassistant-ubus-openwrt.svg?style=for-the-badge
[commits]: https://github.com/shakin89/homeassistant-ubus-openwrt/commits/main
[license-shield]: https://img.shields.io/github/license/shakin89/homeassistant-ubus-openwrt.svg?style=for-the-badge
[license]: https://github.com/shakin89/homeassistant-ubus-openwrt/blob/main/LICENSE