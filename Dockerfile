FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    fluidsynth \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p soundfonts output && \
    cp GeneralUser-GS/GeneralUser.sf2 soundfonts/GeneralUser.sf2

ENV PORT=8000

CMD uvicorn server:app --host 0.0.0.0 --port ${PORT}
