# Basis: Python Slim
FROM python:3.9-slim

# System-Tools installieren
# dsniff = enthält arpspoof
# iptables = für Port-Redirection
# iproute2 = für Netzwerk-Checks
# openssl = für Zertifikats-Generierung
RUN apt-get update && apt-get install -y \
    dsniff \
    iptables \
    iproute2 \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Python Libs
RUN pip install requests paho-mqtt

# Arbeitsverzeichnis
WORKDIR /app

# Dateien kopieren
COPY main.py /app/main.py
COPY entrypoint.sh /app/entrypoint.sh

# Skript ausführbar machen
RUN chmod +x /app/entrypoint.sh

# Starten
ENTRYPOINT ["/app/entrypoint.sh"]
