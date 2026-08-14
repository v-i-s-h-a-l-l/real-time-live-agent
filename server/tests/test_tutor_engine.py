"""Unit tests for TutorEngine decisions and state transitions."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.engine import TutorEngine  # noqa: E402
from tutor.prompts import TUTOR_TURN_MARKER, build_tutor_turn_directive  # noqa: E402
from tutor.types import StudentIntent, TeachingMode, TutorState  # noqa: E402


def test_confusion_uses_clarify_and_increments_streak():
    engine = TutorEngine()
    state = TutorState(phase="learning", topic_id="quadratic-formula")
    d1 = engine.decide("I don't understand", state)
    assert d1.mode == TeachingMode.CLARIFY
    assert d1.move.value == "simplify"
    assert state.confusion_streak == 1
    d2 = engine.decide("I'm still confused", state)
    assert d2.mode == TeachingMode.CLARIFY
    assert state.confusion_streak == 2
    assert d2.move.value == "give_example"
    d3 = engine.decide("Still don't get it", state)
    assert state.confusion_streak == 3
    assert d3.move.value == "analogy"
    assert d3.check_understanding is True


def test_hint_progression_increments_hints_used():
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    d = engine.decide("Give me a hint", state)
    assert d.mode == TeachingMode.HINT
    assert d.use_next_hint is True
    assert d.allow_reveal_answer is False
    assert state.hints_used == 1


def test_answer_request_allows_reveal():
    engine = TutorEngine()
    state = TutorState(phase="practice")
    d = engine.decide("Just give me the answer", state)
    assert d.allow_reveal_answer is True


def test_practice_default_is_socratic():
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    d = engine.decide("Solve this question", state)
    assert d.mode == TeachingMode.SOCRATIC
    assert d.allow_reveal_answer is False


def test_student_answer_evaluates():
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    d = engine.decide("I got 5", state)
    assert d.intent == StudentIntent.STUDENT_ANSWER
    assert d.mode == TeachingMode.EVALUATE
    assert state.last_student_answer == "I got 5"


def test_help_request_is_grounded_faq_not_support():
    engine = TutorEngine()
    state = TutorState(phase="learning", topic_title="Euclid's Division Lemma")
    d = engine.decide("How can you help me?", state)
    assert d.intent == StudentIntent.FAQ
    assert d.faq_id == "what_can_you_help"
    assert d.faq_answer is not None
    assert "hint" in d.faq_answer.lower()
    assert "practice" in d.faq_answer.lower()
    assert "customer support" in d.strategy.lower()  # as a prohibition
    assert "bank" not in d.faq_answer.lower()


def test_unrelated_redirects():
    engine = TutorEngine()
    state = TutorState(phase="learning")
    d = engine.decide("Who won the cricket match?", state)
    assert d.mode == TeachingMode.REDIRECT


def test_related_stays_learn():
    engine = TutorEngine()
    state = TutorState(phase="learning")
    d = engine.decide("Where is this used in real life?", state)
    assert d.mode == TeachingMode.LEARN
    assert d.intent == StudentIntent.RELATED_EDUCATIONAL


def test_question_change_resets_hints():
    state = TutorState(phase="practice", current_question_id="q1", hints_used=2)
    state.sync_from_learning_context(
        {"phase": "practice", "questionId": "q2", "topicId": "t1"}
    )
    assert state.current_question_id == "q2"
    assert state.hints_used == 0


def test_directive_separates_visible_and_tutor_only():
    engine = TutorEngine()
    state = TutorState(
        phase="practice",
        topic_title="Quadratic Formula",
        current_question_id="q1",
    )
    decision = engine.decide("Give me a hint", state)
    directive = build_tutor_turn_directive(
        decision=decision,
        state=state,
        learning_context={
            "phase": "practice",
            "question": "Solve x^2 - 5x + 6 = 0",
        },
        tutor_context={
            "questionId": "q1",
            "hints": ["Think about factors of 6.", "Try -2 and -3."],
            "expectedAnswer": "x = 2, 3",
            "solution": ["Factor to (x-2)(x-3)=0"],
        },
        utterance="Give me a hint",
    )
    assert TUTOR_TURN_MARKER in directive
    assert "Think about factors of 6." in directive
    assert "Factor to (x-2)(x-3)=0" not in directive
    assert decision.allow_reveal_answer is False


def test_acknowledgement_does_not_reset_confusion_or_lecture():
    engine = TutorEngine()
    state = TutorState(phase="learning")
    engine.decide("I don't understand", state)
    assert state.confusion_streak == 1
    d = engine.decide("Okay.", state)
    assert d.mode == TeachingMode.ACKNOWLEDGE
    assert d.response_length.value == "micro"
    assert d.check_understanding is False
    assert state.confusion_streak == 1


def test_simple_factual_is_direct_and_short():
    engine = TutorEngine()
    state = TutorState(phase="learning", current_section_title="Quadratic formula")
    d = engine.decide("What is b here?", state)
    assert d.intent == StudentIntent.EXPLANATION
    assert d.move.value == "answer_direct"
    assert d.response_length.value == "short"
    assert d.check_understanding is False


def test_named_concept_is_explained_not_socratic():
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    d = engine.decide("What is a discriminant?", state)
    assert d.intent == StudentIntent.EXPLANATION
    assert d.mode == TeachingMode.LEARN
    assert d.move.value == "explain"


def test_success_is_brief():
    engine = TutorEngine()
    state = TutorState(phase="learning")
    d = engine.decide("Oh, I get it now.", state)
    assert d.intent == StudentIntent.SUCCESS
    assert d.response_length.value == "micro"
    assert d.check_understanding is False


def test_ack_directive_forbids_follow_up_and_sets_length():
    engine = TutorEngine()
    state = TutorState(phase="learning", topic_title="Discriminant")
    decision = engine.decide("Okay.", state)
    directive = build_tutor_turn_directive(
        decision=decision,
        state=state,
        learning_context={"phase": "learning", "sectionTitle": "Discriminant", "visibleContent": "b² − 4ac"},
        tutor_context=None,
        utterance="Okay.",
    )
    assert "Response length: micro" in directive
    assert "Do not add a follow-up question this turn" in directive
    assert TUTOR_TURN_MARKER in directive


def test_answer_request_includes_expected_in_directive():
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    decision = engine.decide("Just tell me the answer", state)
    directive = build_tutor_turn_directive(
        decision=decision,
        state=state,
        learning_context={"phase": "practice", "question": "Solve x^2 - 5x + 6 = 0"},
        tutor_context={
            "expectedAnswer": "x = 2 and x = 3",
            "solution": ["Factor"],
            "hints": ["h1"],
        },
        utterance="Just tell me the answer",
    )
    assert "x = 2 and x = 3" in directive
    assert "You MAY reveal" in directive
