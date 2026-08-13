"""Unit tests for typed text_input → same Tutor Engine / LLMContext."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from protocol import CLIENT_SESSION_CONTEXT, CLIENT_TEXT_INPUT  # noqa: E402
from processors.session_context import SessionContextStore  # noqa: E402
from processors.text_input import parse_text_input  # noqa: E402
from processors.tutor_turn import _last_user_text  # noqa: E402
from tutor.engine import TutorEngine  # noqa: E402
from tutor.types import TeachingMode, TutorState  # noqa: E402


def test_parse_text_input_extracts_fields():
    parsed = parse_text_input(
        {
            "type": CLIENT_TEXT_INPUT,
            "messageId": "m1",
            "text": "Explain this.",
            "speak": False,
        }
    )
    assert parsed == ("Explain this.", "m1", False)


def test_parse_text_input_defaults_speak_true():
    parsed = parse_text_input({"type": CLIENT_TEXT_INPUT, "text": "What is this?"})
    assert parsed == ("What is this?", "", True)


def test_parse_ignores_other_ws_types():
    assert parse_text_input({"type": CLIENT_SESSION_CONTEXT, "text": "nope"}) is None
    assert parse_text_input({"type": CLIENT_TEXT_INPUT, "text": "   "}) is None
    assert parse_text_input("interrupt") is None


def test_typed_hint_uses_same_tutor_engine_and_practice_state():
    store = SessionContextStore()
    store.set_learning_context(
        {
            "phase": "practice",
            "topicId": "quadratic-formula",
            "questionId": "q2",
            "question": "Solve x^2 - 5x + 6 = 0",
        }
    )
    store.set_tutor_context({"questionId": "q2", "hints": ["Think about factors of 6."]})

    utterance = "Give me a hint."
    messages = [
        {"role": "system", "content": "Lumina"},
        {"role": "user", "content": utterance},
    ]
    assert _last_user_text(messages) == utterance

    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q2")
    state.sync_from_learning_context(store.learning_context)
    decision = engine.decide(utterance, state, learning_context=store.learning_context)
    assert decision.mode == TeachingMode.HINT
    assert decision.use_next_hint is True
    assert state.current_question_id == "q2"


def test_typed_this_uses_active_section_context():
    store = SessionContextStore()
    store.set_learning_context(
        {
            "phase": "learning",
            "sectionTitle": "Euclidean Division Lemma",
            "visibleContent": "a = bq + r",
        }
    )
    engine = TutorEngine()
    state = TutorState(phase="learning")
    state.sync_from_learning_context(store.learning_context)
    decision = engine.decide("Explain this more simply.", state)
    assert "current on-screen" in decision.strategy.lower() or decision.mode.value == "clarify"
    assert state.current_section_title == "Euclidean Division Lemma"
