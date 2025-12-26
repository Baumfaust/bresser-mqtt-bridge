#!/bin/bash
# Professional Entrypoint for Bresser MQTT Bridge

echo "🚀 Starting Bresser-Local-Bridge v0.1..."

# 1. SSL Certificate Handling
CERT_FILE="/app/certs/server.pem"
if [ ! -f "$CERT_FILE" ]; then
    echo "🔐 Generating Self-Signed Certificate..."
    mkdir -p /app/certs
    openssl req -new -x509 -keyout "$CERT_FILE" -out "$CERT_FILE" -days 3650 -nodes -subj "/CN=api.proweatherlive.net" 2>/dev/null
fi

# 2. Network Preparation
echo "1" > /proc/sys/net/ipv4/ip_forward
echo "🌐 IP Forwarding enabled."

# 3. Cleanup Function (Triggers on container stop)
cleanup() {
    echo "🛑 Stopping Bridge and cleaning up network..."
    if [ ! -z "$ARP_PID" ]; then
        kill $ARP_PID
    fi
    iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443 2>/dev/null
    echo "✅ Network rules restored. Goodbye!"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 4. ARP Spoofing
if [ "$ENABLE_ARP" == "true" ]; then
    echo "😈 Starting ARP Spoofing on $INTERFACE..."
    arpspoof -i "$INTERFACE" -t "$TARGET_IP" "$ROUTER_IP" > /dev/null 2>&1 &
    ARP_PID=$!
    echo "   ARP Spoofing active (PID: $ARP_PID)"
fi

# 5. IPTables Redirection
# Remove old rules if existing to avoid duplicates
iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443 2>/dev/null
iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443
echo "🔀 IPTables redirection (443 -> 443 local) active."

# 6. Start Python Bridge
echo "🐍 Starting Python Bridge Service..."
python3 -u main.py &
PY_PID=$!

# Wait for Python process
wait $PY_PID
cleanup
