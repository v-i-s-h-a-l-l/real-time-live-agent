"""Structured operational logs. Observability only — no processing side effects."""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger


def ops_event(
    event: str,
    *,
    session_id: str | None = None,
    category: str | None = None,
    duration_ms: int | None = None,
    **extra: Any,
) -> None:
    """Emit one JSON log line. Never pass secrets, tokens, or raw audio."""
    payload: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
    }
    if session_id:
        payload["session_id"] = session_id
    if category:
        payload["category"] = category
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    for key, value in extra.items():
        if value is not None:
            payload[key] = value
    logger.info("ops {}", json.dumps(payload, default=str, ensure_ascii=False))
