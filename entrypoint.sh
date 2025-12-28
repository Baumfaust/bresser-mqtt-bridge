#!/bin/bash
VERSION=${APP_VERSION:-0.4.0}

echo "🚀 Starting Bresser-Local-Bridge v${VERSION} (DNS Mode)..."

# 1. SSL Certificate Handling
CERT_FILE="/app/certs/server.pem"
if [ ! -f "$CERT_FILE" ]; then
    echo "🔐 Generating Self-Signed Certificate for api.proweatherlive.net..."
    mkdir -p /app/certs
    openssl req -new -x509 -keyout "$CERT_FILE" -out "$CERT_FILE" -days 3650 -nodes -subj "/CN=api.proweatherlive.net" 2>/dev/null
fi

# 2. Network Cleanup
# Wir stellen sicher, dass keine alten REDIRECT-Regeln mehr existieren
iptables -t nat -F PREROUTING 2>/dev/null

# 3. Start Python Bridge
echo "🐍 Starting Python Bridge on Port 443..."
exec python3 -u main.py