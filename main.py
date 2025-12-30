#!/usr/bin/env python3
"""
Bresser-Local-Bridge v0.1
Professional transparent proxy for Bresser 7-in-1 stations (Model 7003220).
Features: Persistent MQTT, HA Auto-Discovery, and Extended Sensor Mapping.
"""

import http.server
import ssl
import time
import urllib.parse
import json
import logging
import os
import sys
import requests
import paho.mqtt.client as mqtt

# --- CONFIGURATION ---
APP_VERSION = os.getenv('APP_VERSION', 'dev')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
MQTT_BROKER = os.getenv('MQTT_BROKER', '192.168.178.2')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'home/weather/bresser')
MQTT_USER = os.getenv('MQTT_USER', None)
MQTT_PASS = os.getenv('MQTT_PASS', None)
DISCOVERY_PREFIX = os.getenv('DISCOVERY_PREFIX', 'homeassistant')
REAL_SERVER_URL = "https://api.proweatherlive.net"
CERT_FILE = "/app/certs/server.pem"

# Global variables to track sync status
last_get_time = 0
retry_count = 0

# --- LOGGING SETUP ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WeatherBridge")

# --- PERSISTENT MQTT CLIENT ---
class WeatherMQTTClient:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USER and MQTT_PASS:
            self.client.username_pw_set(MQTT_USER, MQTT_PASS)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.is_connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("✅ MQTT: Connected successfully")
            self.is_connected = True
            send_discovery(self.client)
        else:
            logger.error(f"❌ MQTT: Connection failed (Code {rc})")

    def _on_disconnect(self, client, userdata, disconnect_flags, rc, properties=None):
        self.is_connected = False
        logger.warning("⚠️ MQTT: Disconnected. Trying to reconnect...")

    def start(self):
        # Shortened keepalive (15s) to detect background drops faster
        self.client.connect_async(MQTT_BROKER, MQTT_PORT, 15)
        self.client.loop_start()

    def publish(self, data):
        if self.is_connected:
            json_data = json.dumps(data)
            self.client.publish(MQTT_TOPIC, json_data, qos=1)
            logger.debug(f"MQTT: Data published {json_data}")
        else:
            logger.warning("MQTT: Client not connected, data dropped")

mqtt_bridge = WeatherMQTTClient()

# --- AUTO DISCOVERY ---
def send_discovery(client):
    """Register all 7-in-1 sensors in Home Assistant."""
    sensors = [
        {"id": "indoor_temp", "name": "Indoor Temperature", "unit": "°C", "class": "temperature"},
        {"id": "indoor_humidity", "name": "Indoor Humidity", "unit": "%", "class": "humidity"},
        {"id": "outdoor_temp", "name": "Outdoor Temperature", "unit": "°C", "class": "temperature"},
        {"id": "outdoor_humidity", "name": "Outdoor Humidity", "unit": "%", "class": "humidity"},
        {"id": "pressure_rel", "name": "Pressure (Rel)", "unit": "hPa", "class": "pressure"},
        {"id": "pressure_abs", "name": "Pressure (Abs)", "unit": "hPa", "class": "pressure"},
        {"id": "wind_speed", "name": "Wind Speed", "unit": "m/s", "class": "wind_speed"},
        {"id": "wind_direction", "name": "Wind Direction", "unit": "°", "class": None},
        {"id": "wind_gust", "name": "Wind Gust", "unit": "m/s", "class": "wind_speed"},
        {"id": "rain_rate", "name": "Rain Rate", "unit": "mm/h", "class": "precipitation_intensity"},
        {"id": "rain_daily", "name": "Rain Daily", "unit": "mm", "class": "precipitation"},
        {"id": "uv_index", "name": "UV Index", "unit": None, "class": None},
        {"id": "irradiance", "name": "Irradiance", "unit": "W/m²", "class": "irradiance"},
        {"id": "battery_ok", "name": "Battery Status", "unit": None, "class": "battery"}
    ]

    for s in sensors:
        config_topic = f"{DISCOVERY_PREFIX}/sensor/bresser_{s['id']}/config"
        payload = {
            "name": f"{s['name']}",
            "state_topic": MQTT_TOPIC,
            "value_template": f"{{{{ value_json.{s['id']} }}}}",
            "unique_id": f"bresser_weather_station_{s['id']}",
            "device": {
                "identifiers": ["bresser_weather_station_7003220"],
                "name": "Bresser Weather Station",
                "sw_version": APP_VERSION,
                "manufacturer": "Bresser",
                "model": "7-in-1 Station 1(7003220)"
            }
        }
        if s['unit']: payload["unit_of_measurement"] = s['unit']
        if s['class']: payload["device_class"] = s['class']

        json_payload = json.dumps(payload)
        client.publish(config_topic, json_payload, retain=True)
        logger.debug(f"MQTT Discovery: Published topic: {config_topic} payload: {json_payload} ")
    logger.info("📡 HA Discovery: Sensors registered")

# --- PROXY HANDLER ---
class BresserProxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse incoming station data
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        data = self._parse(query)

        if data:
            logger.info(f"Captured data for Station {data.get('station_id')}")
            mqtt_bridge.publish(data)

        # Relay to the official ProWeatherLive server
        self._relay()

    def _parse(self, params):
        """Map Bresser query parameters to readable sensor names."""
        # Note: Bresser often sends 'temp' instead of 'tp1tm' depending on firmware
        mapping = {
            'tmi': 'indoor_temp',
            'hui': 'indoor_humidity',
            'relbi': 'pressure_rel',
            'absbi': 'pressure_abs',
            'temp': 'outdoor_temp', 
            'hum': 'outdoor_humidity',
            'tp1tm': 'outdoor_temp', 
            'tp1hu': 'outdoor_humidity',
            'tp1wdir': 'wind_direction', 
            'wdir': 'wind_direction',
            'tp1wsp': 'wind_speed', 
            'wind': 'wind_speed',
            'tp1wgu': 'wind_gust', 
            'gust': 'wind_gust',
            'tp1rinrte': 'rain_rate',
            'rain': 'rain_rate',
            'tp1rindaly': 'rain_daily', 
            'dailyrain': 'rain_daily',
            'tp1uvi': 'uv_index', 
            'uv': 'uv_index',
            'tp1sod': 'irradiance', 
            'tp1bt': 'battery_ok', 
            'wsid': 'station_id'
        }
        res = {}
        for b_key, r_key in mapping.items():
            if b_key in params:
                try:
                    val = params[b_key][0]
                    res[r_key] = float(val) if '.' in val else int(val)
                except (ValueError, IndexError):
                    res[r_key] = params[b_key][0]

        return res if 'station_id' in res else None

    def _relay(self):
        """
        Transparent relay: Streams data directly from the server to the station
        without any modifications to headers or body.
        """
        global last_get_time, retry_count
        try:
            current_time = time.time()
            is_get_request = "/api/v01/get" in self.path

            # Maintain our alarm logic
            if is_get_request:
                time_diff = current_time - last_get_time
                if time_diff > 300: retry_count = 1
                else: retry_count += 1
                last_get_time = current_time
                
                if retry_count >= 3:
                    self._send_ha_alert("Problem")
                else:
                    self._send_ha_alert("OK")

            # 1. Open the connection to the real server as a stream
            # We set stream=True to get access to the raw socket data
            with requests.get(f"{REAL_SERVER_URL}{self.path}", stream=True, timeout=10) as r:
                # 2. Send the original status code
                self.send_response(r.status_code)
                
                # 3. Relay ALL original headers exactly as they came from the server
                for header, value in r.headers.items():
                    # We skip 'Transfer-Encoding' because Python's HTTPServer 
                    # handles the chunking/sending logic internally
                    if header.lower() not in ['transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()

                # 4. Stream the raw content directly to the station
                # 'shutil' is great for piping one stream into another
                import shutil
                shutil.copyfileobj(r.raw, self.wfile)

            logger.info(f"Transparent relay finished for: {self.path}")

        except Exception as e:
            logger.error(f"Transparent relay failed: {e}")
            self.send_response(500)
            self.end_headers()

    def _send_ha_alert(self, status):
        """
        Sends a status update to MQTT to notify Home Assistant about sync issues.
        """
        try:
            # status is either "Problem" or "OK"
            mqtt_bridge.publish(status)
            logger.info(f"MQTT Alert sent: {status}")
        except Exception as e:
            logger.error(f"Failed to send MQTT alert: {e}")

    def log_message(self, format, *args): return

if __name__ == "__main__":
    if not os.path.exists(CERT_FILE):
        logger.critical(f"Certificate missing at {CERT_FILE}!")
        sys.exit(1)

    mqtt_bridge.start()

    server = http.server.HTTPServer(('', 443), BresserProxy)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # Support older station TLS handshake if necessary
    ctx.set_ciphers('DEFAULT@SECLEVEL=1')
    ctx.load_cert_chain(CERT_FILE)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)

    logger.info(f"🚀 Bresser Bridge v{APP_VERSION}: Listening for data...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.server_close()