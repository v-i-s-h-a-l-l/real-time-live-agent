"""Conversation policy — human-feel move and length expectations."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.engine import TutorEngine  # noqa: E402
from tutor.types import (  # noqa: E402
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorState,
)


def _decide(utterance: str, *, phase: str = "learning", **state_kw):
    engine = TutorEngine()
    state = TutorState(phase=phase, **state_kw)
    return engine.decide(utterance, state), state


def test_okay_is_micro_ack():
    d, _ = _decide("Okay.")
    assert d.intent == StudentIntent.ACKNOWLEDGEMENT
    assert d.mode == TeachingMode.ACKNOWLEDGE
    assert d.move == ConversationMove.ACKNOWLEDGE
    assert d.response_length == ResponseLength.MICRO
    assert d.check_understanding is False


def test_hmm_is_hesitation_wait():
    d, _ = _decide("Hmm.")
    assert d.intent == StudentIntent.HESITATION
    assert d.move == ConversationMove.WAIT
    assert d.response_length == ResponseLength.MICRO


def test_wait_alone_is_hesitation():
    d, _ = _decide("Wait.")
    assert d.intent == StudentIntent.HESITATION
    assert d.move == ConversationMove.WAIT


def test_wait_why_is_interrupt_recovery():
    d, _ = _decide("Wait, why did you use 5?")
    assert d.intent == StudentIntent.WHY_HOW
    assert "interruption_recovery" in d.notes
    assert d.check_understanding is False


def test_explain_more_deepens():
    d, state = _decide("Explain more.")
    assert d.intent == StudentIntent.DEPTH_MORE
    assert d.move == ConversationMove.DEEPEN
    assert state.depth_preference == "deep"


def test_keep_it_short():
    d, state = _decide("Keep it short.")
    assert d.intent == StudentIntent.DEPTH_SHORT
    assert d.move == ConversationMove.SHORTEN
    assert state.depth_preference == "short"


def test_simpler_example():
    d, _ = _decide("Give me a simpler example.")
    assert d.intent == StudentIntent.DEPTH_SIMPLER
    assert d.move == ConversationMove.GIVE_EXAMPLE


def test_weather_redirects():
    d, state = _decide("What's the weather?")
    assert d.intent == StudentIntent.UNRELATED
    assert d.mode == TeachingMode.REDIRECT
    assert d.response_length == ResponseLength.MICRO
    assert state.off_topic_count == 1


def test_off_topic_wording_varies_with_count():
    engine = TutorEngine()
    state = TutorState(phase="learning")
    d1 = engine.decide("What's the weather?", state)
    d2 = engine.decide("Who won the cricket match?", state)
    assert d1.strategy != d2.strategy


def test_why_stays_short_no_check():
    d, _ = _decide("Why?")
    assert d.intent == StudentIntent.WHY_HOW
    assert d.response_length == ResponseLength.SHORT
    assert d.check_understanding is False
