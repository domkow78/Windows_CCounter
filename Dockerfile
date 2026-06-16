# Dockerfile dla Windows_CCounter
# Kontener do uruchomienia na Raspberry Pi

FROM python:3.11-slim

# Ustaw katalog roboczy
WORKDIR /app

# Zmienna środowiskowa dla strefy czasowej
ENV TZ=Europe/Warsaw

# Zainstaluj zależności systemowe
# i2c-tools: obsługa magistrali I2C dla Automation HAT Mini
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    i2c-tools \
    && rm -rf /var/lib/apt/lists/*

# Skopiuj plik zależności
COPY requirements.txt .

# Zainstaluj zależności Pythona
RUN pip install --no-cache-dir -r requirements.txt

# === WARIANT A: Automation HAT Mini (ZALECANE) ===
# Odkomentuj jeśli używasz nakładki Automation HAT Mini
# RUN pip install --no-cache-dir automationhat

# === WARIANT B: GPIO bezpośrednie ===
# Odkomentuj jeśli podłączasz czujnik bezpośrednio do GPIO
# RUN pip install --no-cache-dir RPi.GPIO gpiozero

# Skopiuj kod źródłowy
COPY src ./src
COPY main.py .
# config.yaml jest dostarczany przez volume w docker-compose.yml

# Utwórz katalogi na dane i logi
RUN mkdir -p data data/backup logs

# Eksponuj porty
EXPOSE 8000    # FastAPI REST API
EXPOSE 8080    # NiceGUI Web UI

# Uruchom aplikację
CMD ["python", "main.py"]
