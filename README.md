# Bresser Weather Station MQTT Bridge (v0.1) 🌦️🛰️

A professional-grade local bridge for Bresser/CCL weather stations. This project intercepts HTTPS traffic from your station and forwards it to Home Assistant via MQTT, keeping your data local while maintaining cloud functionality for the console's forecast.

## 🚀 Features

- **100% Local Data**: No cloud dependency for your automation 🏠.
- **HA Auto-Discovery**: Sensors appear automatically in Home Assistant with correct units and device classes 🤖.
- **Transparent Proxy**: Maintains console functionality (forecasts/icons) by relaying traffic to the original servers 🔄.
- **Persistent MQTT**: High-performance connection handling with automatic reconnection logic ⚡.
- **Dockerized**: Easy deployment on any Linux-based system (Arch, Debian, Raspberry Pi) 🐳.

## 🛠 How It Works

This bridge utilizes several networking techniques to "liberate" your weather data:

1. **ARP Spoofing**: The server acts as a gateway for the station to intercept outgoing traffic.
2. **SSL Interception**: A Python-based proxy uses a self-signed certificate to decrypt the station's data (exploiting the lack of certificate validation in IoT firmware).
3. **MQTT Bridge**: Extracted sensor data is published as a JSON payload to your MQTT broker (e.g., Mosquitto).



## 📦 Installation

### 1. Clone the repository
```bash
git clone [https://github.com/YOUR_USER/bresser-mqtt-bridge.git](https://github.com/YOUR_USER/bresser-mqtt-bridge.git)
cd bresser-mqtt-bridge
