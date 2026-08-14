"""Session tokens, origin checks, abuse limits, and payload signing.

Keeps the voice pipeline unchanged: this module only gates who may open a
socket and whether client lesson payloads are authentic.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
import uuid
from collections import defaultdict
from typing import Any

import config
from config import TEXT_INPUT_MAX_CHARS

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_NOT_READY = 4408
WS_CLOSE_RATE_LIMITED = 4429
WS_CLOSE_CAPACITY = 1013

TOKEN_TTL_SECS = 2 * 60 * 60
VOICE_TICKET_TTL_SECS = 90
TUTOR_CONTEXT_TTL_SECS = 60 * 60

_CONTROL_MARKERS = re.compile(
    r"\[(?:SESSION_CONTEXT|LEARNING_CONTEXT|TUTOR_TURN|SAFETY_PROTOCOL|"
    r"FAQ_KNOWLEDGE|USER_WANTS_REPEAT|BACKGROUND)\]",
    re.IGNORECASE,
)

_FIELD_LIMITS = {
    "classLabel": 80,
    "classId": 80,
    "subjectName": 80,
    "subjectId": 80,
    "chapterTitle": 160,
    "chapterId": 80,
    "topicTitle": 200,
    "topicId": 80,
    "topicDescription": 500,
    "sectionTitle": 200,
    "sectionId": 80,
    "visibleContent": 800,
    "question": 400,
    "progressLabel": 80,
    "questionId": 80,
}


def canonical_json(value: Any) -> str:
    """Stable JSON used for HMAC (Python + Next.js must match)."""
    return json.dumps(_canonical(value), ensure_ascii=False, separators=(",", ":"))


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items())
            if item is not None
        }
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    return value


def _hmac_hex(body: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def mint_session_token(*, ttl_secs: int = TOKEN_TTL_SECS, now: float | None = None) -> str | None:
    """Legacy HMAC token (exp.sig). Prefer mint_voice_ticket for /ws."""
    secret = config.SESSION_SECRET
    if not secret:
        return None
    exp = int((now if now is not None else time.time()) + ttl_secs)
    body = str(exp)
    return f"{body}.{_hmac_hex(body, secret)}"


def verify_session_token(token: str | None, *, now: float | None = None) -> bool:
    parsed = parse_voice_ticket(token, now=now)
    return parsed is not None


def mint_voice_ticket(
    *,
    user_id: str,
    ttl_secs: int | None = None,
    now: float | None = None,
) -> str | None:
    """Short-lived single-use voice credential: v1.exp.jti.sub.sig"""
    secret = config.SESSION_SECRET
    if not secret or not user_id or "." in user_id:
        return None
    ttl = ttl_secs if ttl_secs is not None else config.VOICE_TICKET_TTL_SECS
    exp = int((now if now is not None else time.time()) + ttl)
    jti = uuid.uuid4().hex
    body = f"v1.{exp}.{jti}.{user_id}"
    return f"{body}.{_hmac_hex(body, secret)}"


def parse_voice_ticket(
    token: str | None,
    *,
    now: float | None = None,
) -> dict[str, str] | None:
    secret = config.SESSION_SECRET
    if not token or not secret:
        return None
    parts = token.split(".")
    if len(parts) != 5 or parts[0] != "v1":
        return None
    _ver, exp_s, jti, user_id, signature = parts
    if not exp_s.isdigit() or not jti or not user_id or not signature:
        return None
    body = f"v1.{exp_s}.{jti}.{user_id}"
    expected = _hmac_hex(body, secret)
    if not hmac.compare_digest(signature, expected):
        return None
    if int(exp_s) < int(now if now is not None else time.time()):
        return None
    return {"jti": jti, "user_id": user_id, "exp": exp_s}


def sign_tutor_context(payload: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    secret = config.SESSION_SECRET
    if not secret:
        return dict(payload)
    signed = dict(payload)
    signed["exp"] = int((now if now is not None else time.time()) + TUTOR_CONTEXT_TTL_SECS)
    body = canonical_json(signed)
    signed["sig"] = _hmac_hex(body, secret)
    return signed


def verify_tutor_context(raw: dict[str, Any], *, now: float | None = None) -> dict[str, Any] | None:
    """Return the trusted payload, or None if a signature is required and invalid."""
    secret = config.SESSION_SECRET
    if not secret:
        return {key: value for key, value in raw.items() if key != "sig"}
    signature = raw.get("sig")
    if not isinstance(signature, str) or not signature:
        return None
    unsigned = {key: value for key, value in raw.items() if key != "sig"}
    expected = _hmac_hex(canonical_json(unsigned), secret)
    if not hmac.compare_digest(signature, expected):
        return None
    exp = unsigned.get("exp")
    if not isinstance(exp, (int, float)) or exp < (now if now is not None else time.time()):
        return None
    return unsigned


def origin_allowed(origin: str | None) -> bool:
    if config.FRONTEND_ORIGINS == ["*"]:
        return not config.is_production()
    if not origin:
        return not config.is_production()
    allowed = {item.rstrip("/") for item in config.FRONTEND_ORIGINS}
    return origin.rstrip("/") in allowed


def token_required() -> bool:
    if config.is_production():
        return True
    if config.ALLOW_ANONYMOUS_WS:
        return False
    return bool(config.SESSION_SECRET)


def tutor_context_signature_required() -> bool:
    return bool(config.SESSION_SECRET) and (
        config.is_production() or not config.ALLOW_ANONYMOUS_WS
    )


def sanitize_client_text(value: Any, *, limit: int = 400) -> str:
    text = _CONTROL_MARKERS.sub("", str(value or ""))
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit]
    return text


def sanitize_client_dict(raw: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key in {"learningObjectives", "keyPoints", "formulas", "prerequisites", "commonMistakes", "topicHints", "hints", "solution", "acceptedAnswers"}:
            if isinstance(value, list):
                limit = 200 if key in {"hints", "solution", "acceptedAnswers"} else 160
                cleaned[key] = [sanitize_client_text(item, limit=limit) for item in value[:8]]
            continue
        if isinstance(value, str):
            cleaned[key] = sanitize_client_text(value, limit=_FIELD_LIMITS.get(key, 200))
        elif isinstance(value, (int, float, bool)) or value is None:
            cleaned[key] = value
        elif isinstance(value, dict):
            continue
        else:
            cleaned[key] = value
    return cleaned


def clip_text_input(text: str) -> str:
    trimmed = text.strip()
    if len(trimmed) <= TEXT_INPUT_MAX_CHARS:
        return trimmed
    return trimmed[:TEXT_INPUT_MAX_CHARS]


def redact_utterance(text: str, *, limit: int = 80) -> str:
    if config.is_production():
        return f"chars={len(text or '')}"
    snippet = (text or "")[:limit]
    return repr(snippet)


class SessionLimiter:
    """In-process connection cap and per-IP connect rate."""

    def __init__(
        self,
        *,
        max_sessions: int | None = None,
        max_per_ip_per_min: int | None = None,
    ) -> None:
        self._max_sessions = (
            max_sessions if max_sessions is not None else config.MAX_CONCURRENT_SESSIONS
        )
        self._max_per_ip = (
            max_per_ip_per_min
            if max_per_ip_per_min is not None
            else config.MAX_CONNECTS_PER_IP_PER_MIN
        )
        self._lock = threading.Lock()
        self._active: set[str] = set()
        self._ip_hits: dict[str, list[float]] = defaultdict(list)

    def acquire(self, session_id: str, ip: str, *, now: float | None = None) -> str | None:
        """Return a close-reason code, or None if the session may start."""
        moment = now if now is not None else time.time()
        with self._lock:
            hits = [stamp for stamp in self._ip_hits[ip] if moment - stamp < 60.0]
            if len(hits) >= self._max_per_ip:
                self._ip_hits[ip] = hits
                return "rate_limited"
            if len(self._active) >= self._max_sessions:
                return "capacity"
            hits.append(moment)
            self._ip_hits[ip] = hits
            self._active.add(session_id)
            return None

    def release(self, session_id: str) -> None:
        with self._lock:
            self._active.discard(session_id)

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)


session_limiter = SessionLimiter()
