# Render / Docker — FastAPI + Pipecat voice backend
#
# Build context: repository root (parent of server/)
# Native Render deploy uses render.yaml at repo root instead of this file.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0

WORKDIR /app

# Pipecat / Silero may need basic audio libs; keep minimal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY server/ ./server/

EXPOSE 8805

# Render sets $PORT; local Docker can override: docker run -e PORT=8805 ...
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8805} --app-dir server
