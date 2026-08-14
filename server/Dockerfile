# Lumina voice backend — production image for Render (CPU).
#
# Build from the repository root:
#   docker build -f server/Dockerfile -t lumina-backend .
#
# Run (secrets via env, never baked in):
#   docker run --rm -e PORT=8805 -p 8805:8805 --env-file .env lumina-backend
#
# Python 3.12 matches requires-python (>=3.12,<3.13) and Render PYTHON_VERSION.

# ---------------------------------------------------------------------------
# Builder: install Python deps into a venv (wheels only; CPU torch).
# ---------------------------------------------------------------------------
FROM python:3.12.10-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Compilers only in the builder, in case a wheel is missing (argon2/scipy).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# CPU PyTorch index is declared in requirements.txt (--extra-index-url).
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Optional RNNoise: prebuilt librnnoise.so inside the pyrnnoise wheel.
# --no-deps avoids audiolab/PyAV; the app loads the .so via ctypes.
# Safe if RNNOISE_ENABLED=false (processor fail-safe passthrough).
RUN pip install --no-cache-dir --no-deps "pyrnnoise>=0.4.3"

# ---------------------------------------------------------------------------
# Runtime: no compilers, non-root, stdout logging.
# ---------------------------------------------------------------------------
FROM python:3.12.10-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/home/lumina \
    XDG_CACHE_HOME=/home/lumina/.cache

# Runtime libs:
#   libgomp1     — OpenMP for numpy / scipy / torch
#   libsndfile1  — soundfile (Pipecat audio utilities)
#   ca-certificates — TLS to Sarvam / Cerebras / Groq / Cartesia
# FFmpeg is not used by this backend (raw PCM over WebSocket).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        libsndfile1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 lumina \
    && useradd --system --uid 10001 --gid lumina --home-dir /home/lumina --create-home lumina

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Application code only (tests/scripts/data excluded via .dockerignore).
COPY --chown=lumina:lumina server/ /app/server/

# SQLite auth store path (AUTH_DB_PATH default). Ephemeral on Render.
# Strip CRLF so the entrypoint works if checked out on Windows.
RUN mkdir -p /app/server/data /home/lumina/.cache \
    && chown -R lumina:lumina /app/server/data /home/lumina \
    && sed -i 's/\r$//' /app/server/docker-entrypoint.sh \
    && chmod +x /app/server/docker-entrypoint.sh

USER lumina

# Local default; Render overrides with $PORT.
EXPOSE 8805

# Existing GET /health — no STT/LLM/TTS calls.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8805'), timeout=3)"

ENTRYPOINT ["/app/server/docker-entrypoint.sh"]
