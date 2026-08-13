import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives at the project root (one level above server/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
# Optional second Cerebras account. Cerebras rate-limits per key, so a second
# key absorbs "queue_exceeded" bursts on the same model before leaving the
# provider. Failover order: Cerebras → Cerebras 2 → Groq.
CEREBRAS_API_KEY_2 = os.getenv("CEREBRAS_API_KEY_2")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8805))

# Comma-separated Vercel (or other) origins, e.g. https://app.example.com
# Empty → allow all origins so local Next.js on :3000 can connect. Set this
# in production; a wildcard CORS policy is not a substitute for auth.
_frontend = os.getenv("FRONTEND_ORIGIN", "").strip()
FRONTEND_ORIGINS = [o.strip() for o in _frontend.split(",") if o.strip()] or ["*"]

DEFAULT_SESSION_LANGUAGE = os.getenv("DEFAULT_SESSION_LANGUAGE", "en-IN")
LANGUAGE_MIN_CHARS = int(os.getenv("LANGUAGE_MIN_CHARS", "8"))
LANGUAGE_MIN_CONFIDENCE = float(os.getenv("LANGUAGE_MIN_CONFIDENCE", "0.55"))
# Hysteresis: consecutive confident detections before an *ambiguous* switch.
# Unambiguous evidence (a full sentence in a new script) and explicit requests
# switch immediately regardless — see LanguageTrackerProcessor.
LANGUAGE_CONFIRMATIONS = int(os.getenv("LANGUAGE_CONFIRMATIONS", "2"))

LLM_MODEL = "gpt-oss-120b"
SAMPLE_RATE = 16000

# Every key a tutoring session needs end to end: speech in, reasoning, speech
# out. GROQ_API_KEY is deliberately absent — it only powers LLM failover, so a
# session still works without it.
_REQUIRED_KEYS = {
    "SARVAM_API_KEY": SARVAM_API_KEY,
    "CEREBRAS_API_KEY": CEREBRAS_API_KEY,
    "CARTESIA_API_KEY": CARTESIA_API_KEY,
}


def missing_required_keys() -> list[str]:
    """Names of the credentials a session cannot start without."""
    return sorted(name for name, value in _REQUIRED_KEYS.items() if not value)


ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()


def is_production() -> bool:
    return ENVIRONMENT in {"production", "prod"}


def collect_pipeline_metrics() -> bool:
    """Per-frame Pipecat metrics. Off in production; they do not affect audio."""
    return not is_production()


def config_warnings() -> list[str]:
    """Misconfiguration that still lets a session start, but should not ship."""
    notes: list[str] = []
    if is_production() and FRONTEND_ORIGINS == ["*"]:
        notes.append(
            "FRONTEND_ORIGIN is unset in production; CORS allows all origins."
        )
    return notes


# Development-only: log the exact text sent toward Cartesia (never audio/keys).
DEBUG_TTS_INPUT = os.getenv("DEBUG_TTS_INPUT", "").lower() in {
    "1",
    "true",
    "yes",
} or not is_production()
