import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives at the project root (one level above server/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
RINGG_API_KEY = os.getenv("RINGG_API_KEY")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8805))

# Comma-separated Vercel (or other) origins, e.g. https://ministros.vercel.app
_frontend = os.getenv("FRONTEND_ORIGIN", "").strip()
FRONTEND_ORIGINS = [o.strip() for o in _frontend.split(",") if o.strip()] or ["*"]

LLM_MODEL = "gpt-oss-120b"
SAMPLE_RATE = 16000
