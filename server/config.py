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

# Shared with Next.js. Signs short-lived /ws tokens, JWTs, and tutor_context.
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
# Dedicated JWT key. Falls back to SESSION_SECRET so existing deploys keep working.
AUTH_SECRET = os.getenv("AUTH_SECRET", "").strip()
JWT_ISSUER = os.getenv("JWT_ISSUER", "lumina").strip() or "lumina"
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "lumina-app").strip() or "lumina-app"
ACCESS_TTL_SECS = int(os.getenv("ACCESS_TTL_SECS", str(15 * 60)))
REFRESH_TTL_SECS = int(os.getenv("REFRESH_TTL_SECS", str(14 * 24 * 60 * 60)))
VOICE_TICKET_TTL_SECS = int(os.getenv("VOICE_TICKET_TTL_SECS", "90"))
REDIS_URL = os.getenv("REDIS_URL", "").strip()
AUTH_DB_PATH = os.getenv(
    "AUTH_DB_PATH",
    str(Path(__file__).resolve().parent / "data" / "auth.sqlite"),
)


def auth_secret() -> str:
    return AUTH_SECRET or SESSION_SECRET

# Comma-separated Vercel (or other) origins, e.g. https://app.example.com
# Development: empty → allow all origins so local Next.js on :3000 can connect.
# Production: empty → no wildcard; FRONTEND_ORIGIN must be set explicitly.
_frontend = os.getenv("FRONTEND_ORIGIN", "").strip()
_parsed_frontend = [o.strip() for o in _frontend.split(",") if o.strip()]
ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
if _parsed_frontend:
    FRONTEND_ORIGINS = _parsed_frontend
elif ENVIRONMENT in {"production", "prod"}:
    FRONTEND_ORIGINS = []
else:
    FRONTEND_ORIGINS = ["*"]

MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "20"))
MAX_CONNECTS_PER_IP_PER_MIN = int(os.getenv("MAX_CONNECTS_PER_IP_PER_MIN", "8"))
TEXT_INPUT_MAX_CHARS = int(os.getenv("TEXT_INPUT_MAX_CHARS", "2000"))
MAX_PCM_ACCUMULATOR_BYTES = int(os.getenv("MAX_PCM_ACCUMULATOR_BYTES", str(64 * 1024)))

DEFAULT_SESSION_LANGUAGE = os.getenv("DEFAULT_SESSION_LANGUAGE", "en-IN")
LANGUAGE_MIN_CHARS = int(os.getenv("LANGUAGE_MIN_CHARS", "8"))
LANGUAGE_MIN_CONFIDENCE = float(os.getenv("LANGUAGE_MIN_CONFIDENCE", "0.55"))
# Hysteresis: consecutive confident detections before an *ambiguous* switch.
# Unambiguous evidence (a full sentence in a new script) and explicit requests
# switch immediately regardless — see LanguageTrackerProcessor.
LANGUAGE_CONFIRMATIONS = int(os.getenv("LANGUAGE_CONFIRMATIONS", "2"))

# Optional server-side noise suppression (RNNoise). Off by default for A/B testing.
RNNOISE_ENABLED = os.getenv("RNNOISE_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}

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


def is_production() -> bool:
    return ENVIRONMENT in {"production", "prod"}


def collect_pipeline_metrics() -> bool:
    """Per-frame Pipecat metrics. Off in production; they do not affect audio."""
    return not is_production()


# Local engine-debug UI may connect without a token only when SESSION_SECRET
# is unset. Once a secret exists (Next.js tutor), voice tickets are required.
_allow_anon = os.getenv("ALLOW_ANONYMOUS_WS", "").strip().lower()
if _allow_anon in {"1", "true", "yes"}:
    ALLOW_ANONYMOUS_WS = True
elif _allow_anon in {"0", "false", "no"}:
    ALLOW_ANONYMOUS_WS = False
else:
    ALLOW_ANONYMOUS_WS = not is_production() and not SESSION_SECRET


def config_warnings() -> list[str]:
    """Misconfiguration that still lets a session start, but should not ship."""
    notes: list[str] = []
    if is_production() and (FRONTEND_ORIGINS == ["*"] or not FRONTEND_ORIGINS):
        notes.append(
            "FRONTEND_ORIGIN is unset in production; authenticated APIs must not use wildcard CORS."
        )
    if is_production() and not SESSION_SECRET:
        notes.append("SESSION_SECRET is unset in production; WebSocket auth cannot run.")
    if is_production() and not auth_secret():
        notes.append("AUTH_SECRET/SESSION_SECRET is unset; user authentication cannot run.")
    if is_production() and not REDIS_URL:
        notes.append(
            "REDIS_URL is unset; auth rate limits use local SQLite and will not share across instances."
        )
    return notes


def production_blockers() -> list[str]:
    """Conditions that must fail /ready and /ws in production."""
    if not is_production():
        return []
    notes: list[str] = []
    if FRONTEND_ORIGINS == ["*"] or not FRONTEND_ORIGINS:
        notes.append("FRONTEND_ORIGIN")
    if not SESSION_SECRET:
        notes.append("SESSION_SECRET")
    if not auth_secret():
        notes.append("AUTH_SECRET")
    if ALLOW_ANONYMOUS_WS:
        notes.append("ALLOW_ANONYMOUS_WS")
    return notes


# Opt-in only — never default on, including in development.
DEBUG_TTS_INPUT = os.getenv("DEBUG_TTS_INPUT", "").lower() in {
    "1",
    "true",
    "yes",
}
