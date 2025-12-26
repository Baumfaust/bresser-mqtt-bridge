#!/bin/bash
# Entrypoint for Bresser MQTT Bridge 

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

# 3. Cleanup Function
cleanup() {
    echo "🛑 Stopping Bridge and cleaning up network..."
    pkill -f arpspoof
    iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443 2>/dev/null
    iptables -D FORWARD -i "$INTERFACE" -j ACCEPT 2>/dev/null
    echo "✅ Network rules restored. Goodbye!"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 4. Aggressive Bi-Directional ARP Spoofing
if [ "$ENABLE_ARP" == "true" ]; then
    echo "😈 Starting Bi-Directional ARP Spoofing on $INTERFACE..."
    # We run two continuous processes. 
    # -r tells arpspoof to be even more persistent in some versions
    arpspoof -i "$INTERFACE" -t "$TARGET_IP" "$ROUTER_IP" > /dev/null 2>&1 &
    arpspoof -i "$INTERFACE" -t "$ROUTER_IP" "$TARGET_IP" > /dev/null 2>&1 &
    echo "   ARP Heartbeat active."
fi

# 5. IPTables Redirection & Forwarding
iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443 2>/dev/null
iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443
iptables -A FORWARD -i "$INTERFACE" -j ACCEPT
echo "🔀 IPTables redirection & forwarding active."

# 6. Start Python Bridge
echo "🐍 Starting Python Bridge Service..."
python3 -u main.py &
PY_PID=$!
echo "🐍 Python Bridge running (PID: $PY_PID)"

# Wait for the Python process to finish or for a signal (SIGTERM/SIGINT)
# The 'wait' command will be interrupted by the trap
wait $PY_PID

# Execute cleanup explicitly if Python exits by itself
cleanup