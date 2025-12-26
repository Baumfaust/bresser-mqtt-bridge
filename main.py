#!/usr/bin/env python3
"""
Bresser-Local-Bridge
A professional transparent proxy with Home Assistant Auto-Discovery.
"""

import http.server
import ssl
import urllib.parse
import json
import threading
import logging
import os
import sys
import requests
import paho.mqtt.client as mqtt

# --- CONFIGURATION & ENV VARIABLES ---
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
MQTT_BROKER = os.getenv('MQTT_BROKER', '192.168.178.50')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'home/weather/bresser')
MQTT_USER = os.getenv('MQTT_USER', None)
MQTT_PASS = os.getenv('MQTT_PASS', None)
DISCOVERY_PREFIX = os.getenv('DISCOVERY_PREFIX', 'homeassistant')
REAL_SERVER_URL = "https://api.proweatherlive.net"
CERT_FILE = os.getenv('CERT_FILE', 'server.pem')

# --- LOGGING SETUP ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WeatherBridge")

class BresserTransparentProxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self._process_request()

    def do_POST(self):
        self._process_request()

    def _process_request(self):
        query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        extracted_data = self._parse_bresser_data(query_params)

        if extracted_data:
            logger.info(f"Captured data for Station {extracted_data.get('station_id', 'Unknown')}")
            threading.Thread(target=publish_to_mqtt, args=(extracted_data,), daemon=True).start()

        self._forward_to_cloud()

    def _forward_to_cloud(self):
        target_url = f"{REAL_SERVER_URL}{self.path}"
        try:
            response = requests.get(target_url, timeout=10)
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'content-length', 'connection']:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.content)
        except Exception as e:
            logger.error(f"Failed to relay to ProWeatherLive: {e}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"success")

    def _parse_bresser_data(self, params):
        mapping = {
            'tmi': 'indoor_temp', 'hui': 'indoor_humidity', 'relbi': 'pressure_rel',
            'temp': 'outdoor_temp', 'hum': 'outdoor_humidity', 'wind': 'wind_speed',
            'gust': 'wind_gust', 'rain': 'rain_rate', 'dailyrain': 'rain_daily',
            'uv': 'uv_index', 'solarradiation': 'solar_radiation', 'tp1bt': 'battery_ok',
            'wsid': 'station_id'
        }
        data = {}
        for b_key, r_key in mapping.items():
            if b_key in params:
                try:
                    val = params[b_key][0]
                    data[r_key] = float(val) if '.' in val else int(val)
                except ValueError:
                    data[r_key] = val
        return data

    def log_message(self, format, *args): return

def send_discovery():
    """Sends MQTT Discovery payloads so HA creates sensors automatically."""
    sensors = [
        {"id": "indoor_temp", "name": "Indoor Temperature", "unit": "°C", "class": "temperature"},
        {"id": "indoor_humidity", "name": "Indoor Humidity", "unit": "%", "class": "humidity"},
        {"id": "outdoor_temp", "name": "Outdoor Temperature", "unit": "°C", "class": "temperature"},
        {"id": "outdoor_humidity", "name": "Outdoor Humidity", "unit": "%", "class": "humidity"},
        {"id": "pressure_rel", "name": "Pressure", "unit": "hPa", "class": "pressure"},
        {"id": "wind_speed", "name": "Wind Speed", "unit": "m/s", "class": "wind_speed"},
        {"id": "battery_ok", "name": "Battery Status", "unit": None, "class": "battery"}
    ]
    
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USER and MQTT_PASS: client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.connect(MQTT_BROKER, MQTT_PORT, 60)

        for s in sensors:
            config_topic = f"{DISCOVERY_PREFIX}/sensor/bresser_{s['id']}/config"
            payload = {
                "name": f"Bresser {s['name']}",
                "state_topic": MQTT_TOPIC,
                "value_template": f"{{{{ value_json.{s['id']} }}}}",
                "unique_id": f"bresser_ws_{s['id']}",
                "device": {
                    "identifiers": ["bresser_weather_station"],
                    "name": "Bresser Weather Station",
                    "model": "7-in-1 Station",
                    "manufacturer": "Bresser"
                }
            }
            if s['unit']: payload["unit_of_measurement"] = s['unit']
            if s['class']: payload["device_class"] = s['class']
            
            client.publish(config_topic, json.dumps(payload), retain=True)
        
        client.disconnect()
        logger.info("📡 Home Assistant Discovery payloads sent.")
    except Exception as e:
        logger.error(f"Discovery failed: {e}")

def publish_to_mqtt(data):
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USER and MQTT_PASS: client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(MQTT_TOPIC, json.dumps(data))
        client.disconnect()
        logger.debug(f"Data published to MQTT: {MQTT_TOPIC}")
    except Exception as e:
        logger.error(f"MQTT Publish failed: {e}")

def start_proxy():
    if not os.path.exists(CERT_FILE):
        logger.critical(f"Certificate file {CERT_FILE} not found.")
        sys.exit(1)

    # Send discovery in a background thread at startup
    threading.Thread(target=send_discovery, daemon=True).start()

    server_address = ('', 443)
    httpd = http.server.HTTPServer(server_address, BresserTransparentProxy)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1
    try: context.set_ciphers('DEFAULT:@SECLEVEL=0')
    except: context.set_ciphers('ALL:!aNULL:!eNULL')
    context.load_cert_chain(certfile=CERT_FILE)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    logger.info(f"🚀 Bridge active on Port 443. MQTT: {MQTT_BROKER}:{MQTT_PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

if __name__ == "__main__":
    start_proxy()
