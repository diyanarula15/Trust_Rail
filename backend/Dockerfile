# TrustRail backend — FastAPI + Postgres + Redis, with a real ffmpeg binary
# for video frame extraction (pipeline/media.py) and libmagic for MIME
# sniffing (pipeline/ingest.py never trusts a file extension).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# var/trust holds the demo CA + registry signing keys generated on first
# seed; var/artifacts holds published/ingested media. Both must live on a
# volume mounted at this path in production — an ephemeral filesystem here
# silently mints new keys (invalidating every signature) on every redeploy.
RUN mkdir -p var/trust var/artifacts

EXPOSE 8000

CMD alembic upgrade head && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
