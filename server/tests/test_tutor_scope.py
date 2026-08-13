"""Scope control — Class 10 maths domain is not negotiable."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.engine import TutorEngine  # noqa: E402
from tutor.intent import detect_intent  # noqa: E402
from tutor.prompts import build_tutor_turn_directive  # noqa: E402
from tutor.types import (  # noqa: E402
    ConversationMove,
    StudentIntent,
    TeachingMode,
    TutorState,
)

TOPIC = "Relationship Between Zeros and Coefficients"


def _engine_state():
    engine = TutorEngine()
    state = TutorState(
        phase="learning",
        topic_title=TOPIC,
        topic_id="zeros-coefficients",
        current_section_title=TOPIC,
        subject="Mathematics",
        application_domain="Class 10 Mathematics Tutor",
    )
    return engine, state


def test_explain_concept_is_maths():
    engine, state = _engine_state()
    d = engine.decide("Explain this concept.", state)
    assert d.intent == StudentIntent.EXPLANATION
    assert d.mode == TeachingMode.LEARN
    assert d.move != ConversationMove.REDIRECT


def test_cricket_redirects_and_does_not_answer():
    engine, state = _engine_state()
    engine.decide("Explain this concept.", state)
    d = engine.decide("Tell me about cricket.", state)
    assert d.intent == StudentIntent.UNRELATED
    assert d.mode == TeachingMode.REDIRECT
    assert d.move == ConversationMove.REDIRECT
    low = d.strategy.lower()
    assert "do not answer" in low
    assert "never say things like" in low
    assert "that's outside our lesson" in low
    assert state.off_topic_count == 1


def test_no_after_cricket_stays_in_maths_domain():
    engine, state = _engine_state()
    engine.decide("Tell me about cricket.", state)
    d = engine.decide("No.", state)
    assert d.intent == StudentIntent.UNRELATED
    assert d.mode == TeachingMode.REDIRECT
    low = d.strategy.lower()
    assert "can't switch" in low or "cannot switch" in low
    assert "do not pause tutoring" in low
    assert state.off_topic_count == 2


def test_insistence_does_not_unlock_general_chat():
    engine, state = _engine_state()
    engine.decide("Tell me about cricket.", state)
    d1 = engine.decide("No, I want to talk about cricket.", state)
    assert d1.intent == StudentIntent.UNRELATED
    assert d1.mode == TeachingMode.REDIRECT
    d2 = engine.decide("Tell me about Dhoni.", state)
    assert d2.intent == StudentIntent.UNRELATED
    assert d2.mode == TeachingMode.REDIRECT
    assert "do not become a general-purpose assistant" in d2.strategy.lower()
    assert d1.strategy != d2.strategy
    assert state.off_topic_count == 3


def test_capital_of_australia_redirects():
    engine, state = _engine_state()
    d = engine.decide("What's the capital of Australia?", state)
    assert d.intent == StudentIntent.UNRELATED
    assert d.mode == TeachingMode.REDIRECT


def test_real_life_zeros_is_educational():
    engine, state = _engine_state()
    d = engine.decide("Where are zeros and coefficients used in real life?", state)
    assert d.intent == StudentIntent.RELATED_EDUCATIONAL
    assert d.mode == TeachingMode.LEARN
    assert d.move != ConversationMove.REDIRECT


def test_another_example_continues_teaching():
    engine, state = _engine_state()
    d = engine.decide("Can you give me another example?", state)
    assert d.intent != StudentIntent.UNRELATED
    assert d.mode != TeachingMode.REDIRECT


def test_standalone_no_does_not_leave_maths():
    engine, state = _engine_state()
    engine.decide("Explain this concept.", state)
    d = engine.decide("No.", state)
    assert d.intent != StudentIntent.UNRELATED
    assert d.mode != TeachingMode.REDIRECT
    assert "stay a" in d.strategy.lower() or "do not" in d.strategy.lower()
    assert "switch domains" in d.strategy.lower()


def test_forget_maths_still_locked():
    engine, state = _engine_state()
    d = engine.decide("Okay, forget maths. Tell me about Dhoni.", state)
    assert d.intent == StudentIntent.UNRELATED
    assert d.mode == TeachingMode.REDIRECT


def test_now_talk_cricket_stays_locked():
    engine, state = _engine_state()
    engine.decide("Tell me about cricket.", state)
    engine.decide("No.", state)
    d = engine.decide("now talk cricket with me", state)
    assert d.intent == StudentIntent.UNRELATED
    assert d.mode == TeachingMode.REDIRECT
    low = d.strategy.lower()
    assert "can't switch" in low or "cannot switch" in low
    assert "do not agree" in low or "never say yes" in low


def test_back_to_maths_resumes_teaching():
    engine, state = _engine_state()
    engine.decide("Tell me about cricket.", state)
    engine.decide("No, I want to talk about cricket.", state)
    d = engine.decide("Okay, let's go back to maths.", state)
    assert d.intent != StudentIntent.UNRELATED
    assert d.mode == TeachingMode.LEARN


def test_conversation_sequence_keeps_maths_identity():
    engine, state = _engine_state()
    turns = [
        ("Explain this concept.", False),
        ("Give me a few examples.", False),
        ("Tell me about cricket.", True),
        ("No, I want to talk about cricket.", True),
        ("Tell me about Dhoni.", True),
        ("Okay, let's go back to maths.", False),
    ]
    for utterance, off_topic in turns:
        d = engine.decide(utterance, state)
        if off_topic:
            assert d.intent == StudentIntent.UNRELATED, utterance
            assert d.mode == TeachingMode.REDIRECT, utterance
        else:
            assert d.intent != StudentIntent.UNRELATED, utterance
            assert d.mode != TeachingMode.REDIRECT, utterance


def test_dhoni_is_unrelated_not_explanation():
    assert detect_intent("Tell me about Dhoni.") == StudentIntent.UNRELATED
    assert detect_intent("Tell me about cricket.") == StudentIntent.UNRELATED
    assert detect_intent("What is a quadratic equation?") == StudentIntent.EXPLANATION


def test_directive_includes_application_domain():
    engine, state = _engine_state()
    decision = engine.decide("Tell me about cricket.", state)
    directive = build_tutor_turn_directive(
        decision=decision,
        state=state,
        learning_context={"phase": "learning", "sectionTitle": TOPIC},
        tutor_context=None,
        utterance="Tell me about cricket.",
    )
    assert "Class 10 Mathematics Tutor" in directive
    assert "Scope lock" in directive
