"""Structured operational logging helper."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loguru import logger

from ops_log import ops_event  # noqa: E402


def test_ops_event_emits_json():
    buf = StringIO()
    sink_id = logger.add(buf, format="{message}")
    try:
        ops_event(
            "ws_open",
            session_id="sess-1",
            category="websocket",
            client_host="127.0.0.1",
        )
        text = buf.getvalue()
        assert "ws_open" in text
        assert "sess-1" in text
        assert "api_key" not in text.lower()
    finally:
        logger.remove(sink_id)
