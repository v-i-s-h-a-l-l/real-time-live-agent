#!/bin/sh
# Render injects PORT. Local docker run can omit it (defaults to 8805).
set -e
PORT="${PORT:-8805}"
exec uvicorn main:app --host 0.0.0.0 --port "$PORT" --app-dir server
