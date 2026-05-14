FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    fluidsynth \
    fluid-soundfont-gm \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p soundfonts output && \
    (curl -L --max-time 120 -o soundfonts/MuseScore_General.sf2 \
    https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2 || \
    echo "MuseScore soundfont download failed, using system FluidR3 fallback")

CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}
