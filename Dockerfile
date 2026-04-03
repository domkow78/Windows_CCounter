# Dockerfile dla Windows_CCounter
# Kontener do uruchomienia na Raspberry Pi

FROM python:3.11-slim

# Ustaw katalog roboczy
WORKDIR /app

# Zmienna środowiskowa dla strefy czasowej
ENV TZ=Europe/Warsaw

# Zainstaluj zależności systemowe potrzebne dla GPIO
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Skopiuj plik zależności
COPY requirements.txt .

# Zainstaluj zależności Pythona
RUN pip install --no-cache-dir -r requirements.txt

# Zainstaluj biblioteki GPIO dla Raspberry Pi
RUN pip install --no-cache-dir RPi.GPIO gpiozero

# Skopiuj kod źródłowy
COPY src ./src
COPY main.py .
COPY config.yaml .

# Utwórz katalogi na dane i logi
RUN mkdir -p data data/backup logs

# Eksponuj port API
EXPOSE 8000

# Uruchom aplikację
CMD ["python", "main.py"]
