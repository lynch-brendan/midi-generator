FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    fluidsynth \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p soundfonts output && \
    curl -L -o soundfonts/MuseScore_General.sf2 \
    https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2

CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}
