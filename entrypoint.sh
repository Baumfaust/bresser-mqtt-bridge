#!/bin/bash
# Use the version from env, fallback to 'unknown'
VERSION=${APP_VERSION:-unknown}

echo "🚀 Starting Bresser-Local-Bridge v${VERSION}..."

# 1. SSL Certificate Handling
CERT_FILE="/app/certs/server.pem"
if [ ! -f "$CERT_FILE" ]; then
    echo "🔐 Generating Self-Signed Certificate..."
    mkdir -p /app/certs
    openssl req -new -x509 -keyout "$CERT_FILE" -out "$CERT_FILE" -days 3650 -nodes -subj "/CN=api.proweatherlive.net" 2>/dev/null
fi

# 2. Network Preparation
echo "1" > /proc/sys/net/ipv4/ip_forward
# Lösche alte Regeln, um Duplikate zu vermeiden
iptables -t nat -F PREROUTING
iptables -F FORWARD

# Die Umleitung: Alles was für Port 443 (HTTPS) reinkommt, muss an unseren Python-Prozess
iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443
# Erlaube das Forwarding für den Rückweg der Cloud-Daten
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -i "$INTERFACE" -j ACCEPT

echo "🌐 Network Routing & IPTables configured."

# 3. Cleanup Function
cleanup() {
    echo "🛑 Cleaning up network..."
    pkill arpspoof
    iptables -t nat -F PREROUTING
    echo "✅ Rules flushed. Exit."
    exit 0
}
trap cleanup SIGINT SIGTERM

# 4. Unidirektionales ARP-Spoofing (Nur Station besprechen)
# Wir sagen der STATION, dass wir der ROUTER sind.
echo "😈 Spoofing Target: $TARGET_IP thinking we are $ROUTER_IP"
arpspoof -i "$INTERFACE" -t "$TARGET_IP" "$ROUTER_IP" > /dev/null 2>&1 &

# 5. Start Python Bridge im Vordergrund
echo "🐍 Starting Python Bridge..."
python3 -u main.py