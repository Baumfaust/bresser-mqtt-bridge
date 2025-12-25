#!/usr/bin/env python3
"""
Bresser-Local-Bridge
A professional transparent proxy for Bresser/CCL Weather Stations.
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
REAL_SERVER_URL = "https://api.proweatherlive.net"
CERT_FILE = os.getenv('CERT_FILE', 'server.pem')

# --- LOGGING SETUP ---
# Configure logging based on the environment variable
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WeatherBridge")

class BresserTransparentProxy(http.server.BaseHTTPRequestHandler):
    """
    HTTP Handler that intercepts weather data and forwards it to the 
    original server to maintain console functionality (forecasts).
    """

    def do_GET(self):
        self._process_request()

    def do_POST(self):
        self._process_request()

    def _process_request(self):
        # 1. Capture local data
        logger.debug(f"Incoming request: {self.path}")
        query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        extracted_data = self._parse_bresser_data(query_params)

        if extracted_data:
            logger.info(f"Captured data for Station {extracted_data.get('station_id', 'Unknown')}")
            logger.debug(f"Full Data Payload: {json.dumps(extracted_data)}")
            # Dispatch MQTT publishing to a separate thread
            threading.Thread(target=publish_to_mqtt, args=(extracted_data,), daemon=True).start()

        # 2. Transparent Relay to keep the weather forecast alive on the station
        self._forward_to_cloud()

    def _forward_to_cloud(self):
        """Relays the request to the real ProWeatherLive server."""
        target_url = f"{REAL_SERVER_URL}{self.path}"
        try:
            logger.debug(f"Relaying request to cloud: {target_url}")
            response = requests.get(target_url, timeout=10)
            
            self.send_response(response.status_code)
            # Forward relevant headers back to the station
            for key, value in response.headers.items():
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'content-length', 'connection']:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.content)
            logger.debug("Cloud response relayed successfully.")
        except Exception as e:
            logger.error(f"Failed to relay to ProWeatherLive: {e}")
            # Even if relay fails, send a generic success to stop the station from retrying infinitely
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"success")

    def _parse_bresser_data(self, params):
        """Maps Bresser keys to readable names."""
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

    def log_message(self, format, *args):
        """Silence the default BaseHTTPRequestHandler logging to use our own."""
        return

def publish_to_mqtt(data):
    """Sends the extracted JSON data to the MQTT broker."""
    try:
        # Using a local client instance for thread safety in simple scripts
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(f"{MQTT_TOPIC}/state", json.dumps(data))
        client.disconnect()
        logger.debug("Data published to MQTT.")
    except Exception as e:
        logger.error(f"MQTT Publish failed: {e}")

def start_proxy():
    if not os.path.exists(CERT_FILE):
        logger.critical(f"Certificate file {CERT_FILE} not found. Shutdown.")
        sys.exit(1)

    server_address = ('', 443)
    httpd = http.server.HTTPServer(server_address, BresserTransparentProxy)
    
    # SSL CONFIGURATION (Legacy Support for IoT)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1
    try:
        context.set_ciphers('DEFAULT:@SECLEVEL=0')
    except:
        context.set_ciphers('ALL:!aNULL:!eNULL')
    
    context.load_cert_chain(certfile=CERT_FILE)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    logger.info(f"🚀 Bridge active. Port: 443 | LogLevel: {LOG_LEVEL}")
    logger.info(f"📡 Forwarding to MQTT Broker: {MQTT_BROKER}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopping...")
        httpd.server_close()

if __name__ == "__main__":
    start_proxy()