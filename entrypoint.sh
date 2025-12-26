#!/bin/bash
# Entrypoint for Bresser MQTT Bridge v0.1

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
    # Kill the ARP loop and arpspoof
    pkill -P $$ 
    iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443 2>/dev/null
    echo "✅ Network rules restored. Goodbye!"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 4. Aggressive ARP Spoofing Loop
if [ "$ENABLE_ARP" == "true" ]; then
    echo "😈 Starting Aggressive ARP Spoofing on $INTERFACE..."
    # Run in a background loop to prevent the router from reclaiming the station
    (
        while true; do
            arpspoof -i "$INTERFACE" -t "$TARGET_IP" "$ROUTER_IP" > /dev/null 2>&1 &
            SPOOF_PID=$!
            sleep 10 # Restart arpspoof every 10 seconds to stay fresh
            kill $SPOOF_PID > /dev/null 2>&1
        done
    ) &
    echo "   ARP Heartbeat active (updates every 10s)"
fi

# 5. IPTables Redirection
iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443 2>/dev/null
iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443
echo "🔀 IPTables redirection (443 -> 443 local) active."

# 6. Start Python Bridge
python3 -u main.py &
PY_PID=$!
echo "🐍 Python Bridge running (PID: $PY_PID)"

# Wait for the Python process to finish or for a signal (SIGTERM/SIGINT)
# The 'wait' command will be interrupted by the trap
wait $PY_PID

# Execute cleanup explicitly if Python exits by itself
cleanup