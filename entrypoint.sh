#!/bin/bash

echo "Starting Bresser-Local-Bridge Docker..."

# 1. SSL Zertifikat generieren (falls nicht vorhanden)
if [ ! -f "server.pem" ]; then
    echo "🔐 Generating Self-Signed Certificate..."
    openssl req -new -x509 -keyout server.pem -out server.pem -days 3650 -nodes -subj "/CN=api.proweatherlive.net" 2>/dev/null
fi

# 2. IP Forwarding aktivieren (WICHTIG für MITM!)
echo "1" > /proc/sys/net/ipv4/ip_forward
echo "🌐 IP Forwarding enabled."

# 3. ARP Spoofing (Optional, falls User DNS nutzt braucht er das nicht)
if [ "$ENABLE_ARP" == "true" ]; then
    if [ -z "$TARGET_IP" ] || [ -z "$ROUTER_IP" ] || [ -z "$INTERFACE" ]; then
        echo "❌ ERROR: ENABLE_ARP is true, but TARGET_IP, ROUTER_IP or INTERFACE is missing!"
        exit 1
    fi
    
    echo "😈 Starting ARP Spoofing on $INTERFACE..."
    echo "   Target (Station): $TARGET_IP"
    echo "   Router: $ROUTER_IP"
    
    # Startet Arpspoof im Hintergrund (&)
    arpspoof -i "$INTERFACE" -t "$TARGET_IP" "$ROUTER_IP" > /dev/null 2>&1 &
    ARP_PID=$!
    echo "   ARP Spoofing running (PID: $ARP_PID)"
fi

# 4. IPTables Redirection (Traffic auf Port 443 abfangen)
# Lösche alte Regeln zur Sicherheit zuerst
iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443 2>/dev/null
# Neue Regel setzen
iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443
echo "🔀 IPTables redirection (443 -> 443 local) active."

# 5. Start Python Script
# Wir nutzen 'exec', damit das Python Skript PID 1 übernimmt (gut für Signale)
echo "🚀 Starting Python Bridge..."
python3 -u main.py &
PY_PID=$!

# Warte auf das Python Skript
wait $PY_PID

# --- AUFRÄUMEN (Wenn der Container gestoppt wird) ---
# Das passiert normalerweise durch Trap-Funktionen, aber hier einfachheitshalber:
echo "🛑 Stopping..."
if [ ! -z "$ARP_PID" ]; then
    kill $ARP_PID
fi
# Regel löschen
iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 443
