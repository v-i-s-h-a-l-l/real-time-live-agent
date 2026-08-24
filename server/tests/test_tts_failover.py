"""Cartesia billing errors fall back to a secondary TTS or text-only."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

from services.tts_failover import (  # noqa: E402
    TTSFailoverController,
    compact_tts_reason,
    is_tts_hard_failure,
)


def test_402_is_a_hard_failure():
    assert is_tts_hard_failure("Cartesia API error (status 402): Payment required")
    assert is_tts_hard_failure("Error: {'type': 'error', 'status': 402}")
    assert is_tts_hard_failure("quota exceeded")
    assert not is_tts_hard_failure("Cartesia connection was disconnected (timeout?)")
    assert not is_tts_hard_failure("websocket closed 1006")


def test_compact_reason_does_not_echo_payload():
    assert compact_tts_reason("Cartesia API error (status 402): sk-secret") == "http_402"


def test_controller_falls_back_when_secondary_exists():
    ctrl = TTSFailoverController(has_fallback=True)
    assert ctrl.consider("status 402") == "fallback"
    assert ctrl.mode == "fallback"
    assert ctrl.consider("status 402") is None


def test_controller_degrades_to_text_without_secondary():
    ctrl = TTSFailoverController(has_fallback=False)
    assert ctrl.consider("Payment required") == "text"
    assert ctrl.mode == "text"


def test_text_only_skip_keeps_transcript_without_audio():
    from pipecat.frames.frames import TextFrame

    from services.tts_failover import apply_text_only_skip

    frame = TextFrame(text="The remainder is 3.")
    apply_text_only_skip(frame)
    assert frame.skip_tts is True


def test_tts_fallback_ops_event_shape():
    buf = StringIO()
    sink_id = logger.add(buf, format="{message}")
    try:
        from ops_log import ops_event

        ops_event(
            "tts_fallback",
            category="tts",
            session_id="sess-1",
            to="text",
            reason="http_402",
        )
        text = buf.getvalue()
        assert "tts_fallback" in text
        assert "http_402" in text
        assert "api_key" not in text.lower()
    finally:
        logger.remove(sink_id)
