#!/bin/bash
# Automatisches Update für die Bresser Bridge

set -e # Stoppt das Skript bei Fehlern

echo "🚀 Stoppe Container..."
docker compose down

echo "📥 Ziehe neueste Änderungen von GitHub..."
git pull

echo "🛠️ Baue Image neu..."
docker compose build

echo "✅ Starte Bridge im Hintergrund..."
docker compose up -d

echo "📜 Zeige Logs (Strg+C zum Beenden)..."
docker logs -f bresser_mqtt_bridge
