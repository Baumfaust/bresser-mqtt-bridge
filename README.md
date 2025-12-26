# Bresser Weather Station MQTT Bridge (v0.2) 🌦️🛰️

A local bridge for Bresser/CCL weather stations. This project intercepts HTTPS traffic from your station and forwards it to Home Assistant via MQTT, keeping your data local while maintaining cloud functionality for the console's forecast.

## 📡 Compatibility & Hardware
This bridge was developed and successfully tested with the following hardware:
- BRESSER 6-Tage 4CAST PRO SF WLAN-Wetterstation 7-in-1 solar (Model: **7003220**)

Since many Bresser and CCL electronics stations use the same communication protocol `proweatherlive.net`, this bridge is likely compatible with other models as well.

## 🚀 Features

- **100% Local Data**: No cloud dependency for your automation 🏠.
- **Homeassistant Auto-Discovery**: Sensors appear automatically in Home Assistant with correct units and device classes 🤖.
- **Transparent Proxy**: Maintains console functionality (forecasts/icons) by relaying traffic to the original servers 🔄.
- **Persistent MQTT**: High-performance connection handling with automatic reconnection logic .
- **Dockerized**: Easy deployment on any Linux-based system (Arch, Debian, Raspberry Pi) 🐳.

## 🛠 How it Works

This bridge utilizes several networking techniques to "liberate" your weather data:

1. **ARP Spoofing**: The server acts as a gateway for the station to intercept outgoing traffic.
2. **SSL Interception**: A Python-based proxy uses a self-signed certificate to decrypt the station's data (exploiting the lack of certificate validation in IoT firmware).
3. **MQTT Bridge**: Extracted sensor data is published as a JSON payload to your MQTT broker.

## 🔐 Security & Secrets
To keep your credentials (like MQTT passwords) safe and prevent them from being accidentally pushed to GitHub, this project uses a .env file.

1. Create a `.env` file in the root directory:
```Bash
MQTT_PASS=your_secure_password
```
In your docker-compose.yml, the password is referenced like this:

```YAML

environment:
  - MQTT_PASS=${MQTT_PASS}
```
Note: The `.gitignore` file is already configured to exclude `.env` and the certs/ folder from being tracked by Git.

## 📦 Installation & Setup

### 1. Prerequisites
Ensure you have **Docker** and **Docker Compose** installed on your host system.

### 2. Clone the Repository
```bash
git clone https://github.com/Baumfaust/bresser-mqtt-bridge.git
cd bresser-mqtt-bridge
```

### 3. Configuration
Edit the `docker-compose.ymy` file to match your network environment:
- `MQTT_BROKER`: IP@ of your MQTT broker (e.g., Mosquitto).
- `TARGET_IP`-: The local IP@ of your Bresser Weather Station.
- `ROUTER_IP`-: Your network gateway (Router) IP.
- `INTERFACE`: The network interface of your server (e.g., `eth0` or `enp1s0`).

### 4. Build and Deploy
Since this project uses a custom entrypoint and system tools, you need to build the image locally:

```bash
# Build the Docker image
docker compose build

# Start the bridge in detached mode
docker compose up -d
```

### 5. Verify the Connection
Check the logs to ensure everything is running correctly:
```bash
docker logs -f bresser_mqtt_bridge
```
You should see `✅ MQTT: Connected successfully` and `🚀 Bresser Bridge v0.1 ready`.

## 📊 Supported Sensors
- 🌡️ Temperature: Indoor & Outdoor
- 💧 Humidity: Indoor & Outdoor
- 🎈 Pressure: Relative air pressure
- 💨 Wind: Speed and Gusts
- 🌧️ Rain: Hourly and Daily rates
- ☀️ Solar: UV Index and Solar Radiation
- 🔋 System: Battery status and Station ID

## 🛠 Troubleshooting
- **Permission Denied**: The bridge requires `privileged: true` to manipulate `iptables`.
- **Port 443 Conflict**: Ensure no other service (like Nginx) is using Port 443 on the host.
- **Data Gap**: If sensors stop updating, verify your ARP spoofing status in the logs.

---
**Disclaimer**: This project is for private use in local networks only.
