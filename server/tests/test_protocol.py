"""The WebSocket wire contract with the browser.

These values are a published protocol, not internal names: renaming one
silently breaks every connected client. The literals below are duplicated on
purpose so a rename cannot pass unnoticed.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import protocol  # noqa: E402


def test_client_message_values_are_the_published_wire_strings():
    assert protocol.CLIENT_INTERRUPT == "interrupt"
    assert protocol.CLIENT_TEXT_INPUT == "text_input"
    assert protocol.CLIENT_TTS_VOICE == "tts_voice"
    assert protocol.CLIENT_SESSION_CONTEXT == "session_context"
    assert protocol.CLIENT_LEARNING_CONTEXT == "learning_context"
    assert protocol.CLIENT_TUTOR_CONTEXT == "tutor_context"
    assert protocol.TEXT_INPUT_USER_ID == "text"


def test_every_client_message_is_registered():
    assert protocol.CLIENT_MESSAGE_TYPES == {
        "interrupt",
        "text_input",
        "tts_voice",
        "session_context",
        "learning_context",
        "tutor_context",
    }


def test_study_break_events_are_the_published_wire_strings():
    assert protocol.SERVER_BREAK_STARTED == "break_started"
    assert protocol.SERVER_BREAK_ENDED == "break_ended"
    assert protocol.SERVER_BREAK_CANCELLED == "break_cancelled"
    assert protocol.SERVER_BREAK_REQUESTING == "break_requesting"
    assert protocol.SERVER_BREAK_MESSAGE == "break_message"
    assert protocol.SERVER_BREAK_EVENT_TYPES == {
        "break_started",
        "break_ended",
        "break_cancelled",
        "break_requesting",
        "break_message",
    }


def test_safety_alert_is_the_published_wire_string():
    assert protocol.SERVER_SAFETY_ALERT == "safety_alert"


def test_message_type_reads_the_type_field():
    assert protocol.message_type({"type": "interrupt"}) == "interrupt"


def test_untrusted_payloads_are_not_control_messages():
    for payload in (None, "interrupt", 42, [], {"type": 7}, {}):
        assert protocol.message_type(payload) is None
        assert not protocol.is_client_message(payload, protocol.CLIENT_INTERRUPT)


def test_is_client_message_does_not_match_a_different_type():
    message = {"type": protocol.CLIENT_TEXT_INPUT, "text": "hello"}
    assert protocol.is_client_message(message, protocol.CLIENT_TEXT_INPUT)
    assert not protocol.is_client_message(message, protocol.CLIENT_INTERRUPT)
