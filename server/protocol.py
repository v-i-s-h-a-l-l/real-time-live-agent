"""Wire protocol for the browser <-> voice engine WebSocket.

The socket carries two kinds of payloads:

* binary  — raw PCM-16 mono audio at ``config.SAMPLE_RATE`` in both
  directions, re-chunked by ``serializers.raw_pcm.RawPCMSerializer``.
* text    — a JSON object with a ``type`` field, handled by exactly one
  processor in the pipeline.

The values below are the wire format and are mirrored by the browser in
``tutor-frontend/src/lib/voice/protocol.ts``. Changing a string here is a
breaking protocol change: update both sides together.

Most server-to-browser events are produced by Pipecat's RTVI processor.
Study-break events are application messages on the same WebSocket
(``OutputTransportMessageFrame``), not a second connection.
"""

from __future__ import annotations

from typing import Any, Final

# ── Browser → server control messages ────────────────────────────────────────

#: Barge-in: the student started speaking, cancel the current bot turn.
CLIENT_INTERRUPT: Final = "interrupt"

#: A typed chat message, routed into the same tutor turn path as speech.
CLIENT_TEXT_INPUT: Final = "text_input"

#: Which Cartesia voice to speak with (validated against ``voices.py``).
CLIENT_TTS_VOICE: Final = "tts_voice"

#: Which topic the student opened.
CLIENT_SESSION_CONTEXT: Final = "session_context"

#: Which slide/section/question is on screen right now.
CLIENT_LEARNING_CONTEXT: Final = "learning_context"

#: Tutor-only material (hints, solutions) that must never be shown on screen.
CLIENT_TUTOR_CONTEXT: Final = "tutor_context"

#: Speaker id the engine attaches to transcriptions that came from typed
#: input rather than the microphone. Mirrored by the browser as
#: ``TEXT_INPUT_USER_ID`` in ``tutor-frontend/src/lib/voice/protocol.ts``.
TEXT_INPUT_USER_ID: Final = "text"

CLIENT_MESSAGE_TYPES: Final[frozenset[str]] = frozenset(
    {
        CLIENT_INTERRUPT,
        CLIENT_TEXT_INPUT,
        CLIENT_TTS_VOICE,
        CLIENT_SESSION_CONTEXT,
        CLIENT_LEARNING_CONTEXT,
        CLIENT_TUTOR_CONTEXT,
    }
)

# ── Server → browser application events (same WebSocket as RTVI) ─────────────

SERVER_BREAK_STARTED: Final = "break_started"
SERVER_BREAK_ENDED: Final = "break_ended"
SERVER_BREAK_CANCELLED: Final = "break_cancelled"
SERVER_BREAK_REQUESTING: Final = "break_requesting"
SERVER_BREAK_MESSAGE: Final = "break_message"

SERVER_BREAK_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        SERVER_BREAK_STARTED,
        SERVER_BREAK_ENDED,
        SERVER_BREAK_CANCELLED,
        SERVER_BREAK_REQUESTING,
        SERVER_BREAK_MESSAGE,
    }
)

#: Adaptive practice state mirror (evaluation, hints, mastery) for the lesson UI.
SERVER_PRACTICE_PROGRESS: Final = "practice_progress"


def message_type(message: Any) -> str | None:
    """Return the control-message type, or None if this is not one.

    Frames arrive from the network, so the payload is untrusted: anything
    that is not a dict with a string ``type`` is simply not a control
    message and is passed along the pipeline untouched.
    """
    if not isinstance(message, dict):
        return None
    value = message.get("type")
    return value if isinstance(value, str) else None


def is_client_message(message: Any, expected: str) -> bool:
    """True when ``message`` is the given control message."""
    return message_type(message) == expected
