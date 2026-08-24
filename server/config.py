import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives at the project root (one level above server/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.getenv("GOOGLE_AI_API_KEY")
)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Optional secondary TTS when Cartesia returns billing/quota errors (402).
# "openai" uses OPENAI_API_KEY. Unset → degrade to transcript-only, not silence.
TTS_FALLBACK_PROVIDER = os.getenv("TTS_FALLBACK_PROVIDER", "").strip().lower()
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

# Local-only demo account. Ignored in production even if set.
ENABLE_DEMO_LOGIN = os.getenv("ENABLE_DEMO_LOGIN", "").strip().lower() in {
    "1",
    "true",
    "yes",
}
DEMO_LOGIN_EMAIL = os.getenv("DEMO_LOGIN_EMAIL", "").strip()
DEMO_LOGIN_PASSWORD = os.getenv("DEMO_LOGIN_PASSWORD", "")


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
# CallMute auto-unmute: hold-on / one-second must not last the whole session.
try:
    CALL_MUTE_TIMEOUT_SECS = int(os.getenv("CALL_MUTE_TIMEOUT_SECS", "40"))
except ValueError:
    CALL_MUTE_TIMEOUT_SECS = 40
if CALL_MUTE_TIMEOUT_SECS <= 0:
    CALL_MUTE_TIMEOUT_SECS = 40
try:
    CALL_MUTE_RESUME_MIN_WORDS = int(os.getenv("CALL_MUTE_RESUME_MIN_WORDS", "6"))
except ValueError:
    CALL_MUTE_RESUME_MIN_WORDS = 6
if CALL_MUTE_RESUME_MIN_WORDS <= 0:
    CALL_MUTE_RESUME_MIN_WORDS = 6
# Tutor awaiting_* escape: same miss-counter + timeout style as CallMute/Safety.
try:
    AWAITING_TIMEOUT_SECS = int(os.getenv("AWAITING_TIMEOUT_SECS", "40"))
except ValueError:
    AWAITING_TIMEOUT_SECS = 40
if AWAITING_TIMEOUT_SECS <= 0:
    AWAITING_TIMEOUT_SECS = 40
try:
    AWAITING_MISS_RESUME_AFTER = int(os.getenv("AWAITING_MISS_RESUME_AFTER", "3"))
except ValueError:
    AWAITING_MISS_RESUME_AFTER = 3
if AWAITING_MISS_RESUME_AFTER <= 0:
    AWAITING_MISS_RESUME_AFTER = 3

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

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
# Model default follows the provider so switching providers "just works".
# Voice: prefer a fast chat model (gpt-5.6-luna). Avoid o-series reasoning
# models — they add seconds of silent thinking before the first spoken token.
_LLM_DEFAULTS = {
    "openai": "gpt-5.6-luna",
    "openrouter": "google/gemma-4-26b-a4b-it:free",
    "gemini": "gemini-2.5-flash",
    "groq": "openai/gpt-oss-120b",
}
LLM_MODEL = os.getenv("LLM_MODEL") or _LLM_DEFAULTS.get(LLM_PROVIDER, "gpt-5.6-luna")
SAMPLE_RATE = 16000


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


# Pipeline timing — env overrides, defaults identical to previous hardcodes.
VAD_START_SECS = _env_float("VAD_START_SECS", 0.2)
VAD_STOP_SECS = _env_float("VAD_STOP_SECS", 1.1)
STT_KEEPALIVE_TIMEOUT_SECS = _env_float("STT_KEEPALIVE_TIMEOUT_SECS", 15.0)
STT_KEEPALIVE_INTERVAL_SECS = _env_float("STT_KEEPALIVE_INTERVAL_SECS", 5.0)
SARVAM_MIN_SPEECH_FRAMES = _env_int("SARVAM_MIN_SPEECH_FRAMES", 6)
SARVAM_NEGATIVE_FRAMES_COUNT = _env_int("SARVAM_NEGATIVE_FRAMES_COUNT", 35)
SARVAM_NEGATIVE_FRAMES_WINDOW = _env_int("SARVAM_NEGATIVE_FRAMES_WINDOW", 48)
SARVAM_PRE_SPEECH_PAD_FRAMES = _env_int("SARVAM_PRE_SPEECH_PAD_FRAMES", 16)
AUDIO_GATE_DECAY_SECS = _env_float("AUDIO_GATE_DECAY_SECS", 0.35)
SILENCE_THRESHOLD_SECS = _env_float("SILENCE_THRESHOLD_SECS", 15.0)
MEDIUM_SILENCE_THRESHOLD_SECS = _env_float("MEDIUM_SILENCE_THRESHOLD_SECS", 120.0)
LONG_SILENCE_THRESHOLD_SECS = _env_float("LONG_SILENCE_THRESHOLD_SECS", 300.0)
USER_TURN_STOP_TIMEOUT_SECS = _env_float("USER_TURN_STOP_TIMEOUT_SECS", 3.0)
LLM_EMPTY_GUARD_TIMEOUT_SECS = _env_float("LLM_EMPTY_GUARD_TIMEOUT_SECS", 20.0)
CARTESIA_TTS_MODEL = os.getenv("CARTESIA_TTS_MODEL", "sonic-3.5").strip() or "sonic-3.5"

# Every key a tutoring session needs end to end: speech in, reasoning, speech out.
_REQUIRED_KEYS: dict[str, str | None] = {
    "SARVAM_API_KEY": SARVAM_API_KEY,
    "CARTESIA_API_KEY": CARTESIA_API_KEY,
}
if LLM_PROVIDER == "gemini":
    _REQUIRED_KEYS["GEMINI_API_KEY"] = GEMINI_API_KEY
elif LLM_PROVIDER == "openrouter":
    _REQUIRED_KEYS["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY
elif LLM_PROVIDER == "openai":
    _REQUIRED_KEYS["OPENAI_API_KEY"] = OPENAI_API_KEY
else:
    _REQUIRED_KEYS["GROQ_API_KEY"] = GROQ_API_KEY


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
    if is_production() and ENABLE_DEMO_LOGIN:
        notes.append(
            "ENABLE_DEMO_LOGIN is set in production and will be ignored; "
            "demo login is local-only."
        )
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
