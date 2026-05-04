FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    fluidsynth \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p soundfonts && \
    curl -L -o soundfonts/GeneralUser.sf2 \
    "https://archive.org/download/generaluser-gs-soundfont/GeneralUser_GS_v1.471.sf2"

RUN mkdir -p output

ENV PORT=8000

CMD uvicorn server:app --host 0.0.0.0 --port ${PORT}
