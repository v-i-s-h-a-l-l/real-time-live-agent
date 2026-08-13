"""Human-feel evaluation suite — expected policy for realistic student utterances."""

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

# utterance, phase, intent, mode, move, length
SUITE: list[tuple[str, str, StudentIntent, TeachingMode, ConversationMove, ResponseLength]] = [
    ("What is a quadratic equation?", "learning", StudentIntent.EXPLANATION, TeachingMode.LEARN, ConversationMove.EXPLAIN, ResponseLength.MEDIUM),
    ("Okay.", "learning", StudentIntent.ACKNOWLEDGEMENT, TeachingMode.ACKNOWLEDGE, ConversationMove.ACKNOWLEDGE, ResponseLength.MICRO),
    ("Hmm.", "learning", StudentIntent.HESITATION, TeachingMode.ACKNOWLEDGE, ConversationMove.WAIT, ResponseLength.MICRO),
    ("Right.", "learning", StudentIntent.ACKNOWLEDGEMENT, TeachingMode.ACKNOWLEDGE, ConversationMove.ACKNOWLEDGE, ResponseLength.MICRO),
    ("I don't understand.", "learning", StudentIntent.CONFUSION, TeachingMode.CLARIFY, ConversationMove.SIMPLIFY, ResponseLength.SHORT),
    ("I'm confused.", "learning", StudentIntent.CONFUSION, TeachingMode.CLARIFY, ConversationMove.SIMPLIFY, ResponseLength.SHORT),
    ("Why?", "learning", StudentIntent.WHY_HOW, TeachingMode.CLARIFY, ConversationMove.ANSWER_DIRECT, ResponseLength.SHORT),
    ("Why do we need this?", "learning", StudentIntent.WHY_HOW, TeachingMode.CLARIFY, ConversationMove.ANSWER_DIRECT, ResponseLength.SHORT),
    ("Why does this work?", "learning", StudentIntent.WHY_HOW, TeachingMode.CLARIFY, ConversationMove.ANSWER_DIRECT, ResponseLength.SHORT),
    ("Wait.", "learning", StudentIntent.HESITATION, TeachingMode.ACKNOWLEDGE, ConversationMove.WAIT, ResponseLength.MICRO),
    ("Hold on.", "learning", StudentIntent.HESITATION, TeachingMode.ACKNOWLEDGE, ConversationMove.WAIT, ResponseLength.MICRO),
    ("Why did you do that?", "learning", StudentIntent.WHY_HOW, TeachingMode.CLARIFY, ConversationMove.ANSWER_DIRECT, ResponseLength.SHORT),
    ("No, I think that's wrong.", "learning", StudentIntent.DISAGREEMENT, TeachingMode.CORRECT, ConversationMove.CORRECT, ResponseLength.SHORT),
    ("I got a different answer.", "practice", StudentIntent.DISAGREEMENT, TeachingMode.CORRECT, ConversationMove.CORRECT, ResponseLength.SHORT),
    ("I think the answer is 3.", "practice", StudentIntent.STUDENT_ANSWER, TeachingMode.EVALUATE, ConversationMove.EVALUATE, ResponseLength.SHORT),
    ("Give me a hint.", "practice", StudentIntent.HINT, TeachingMode.HINT, ConversationMove.HINT, ResponseLength.SHORT),
    ("Another hint.", "practice", StudentIntent.HINT, TeachingMode.HINT, ConversationMove.HINT, ResponseLength.SHORT),
    ("Say that again.", "learning", StudentIntent.REPEAT, TeachingMode.REPEAT, ConversationMove.REPEAT, ResponseLength.SHORT),
    ("Explain that differently.", "learning", StudentIntent.REPEAT, TeachingMode.REPEAT, ConversationMove.REPEAT, ResponseLength.SHORT),
    ("Oh, I get it now.", "learning", StudentIntent.SUCCESS, TeachingMode.ACKNOWLEDGE, ConversationMove.CELEBRATE, ResponseLength.MICRO),
    ("I got it!", "learning", StudentIntent.SUCCESS, TeachingMode.ACKNOWLEDGE, ConversationMove.CELEBRATE, ResponseLength.MICRO),
    ("Where do we use this in real life?", "learning", StudentIntent.RELATED_EDUCATIONAL, TeachingMode.LEARN, ConversationMove.EXPLAIN, ResponseLength.SHORT),
    ("What's the weather?", "learning", StudentIntent.UNRELATED, TeachingMode.REDIRECT, ConversationMove.REDIRECT, ResponseLength.MICRO),
    ("Who won the cricket match?", "learning", StudentIntent.UNRELATED, TeachingMode.REDIRECT, ConversationMove.REDIRECT, ResponseLength.MICRO),
    ("What is this?", "learning", StudentIntent.EXPLANATION, TeachingMode.LEARN, ConversationMove.ANSWER_DIRECT, ResponseLength.SHORT),
    ("Why is that needed?", "learning", StudentIntent.WHY_HOW, TeachingMode.CLARIFY, ConversationMove.ANSWER_DIRECT, ResponseLength.SHORT),
    ("Can you explain that second step?", "learning", StudentIntent.EXPLANATION, TeachingMode.LEARN, ConversationMove.EXPLAIN, ResponseLength.MEDIUM),
    ("Explain more.", "learning", StudentIntent.DEPTH_MORE, TeachingMode.LEARN, ConversationMove.DEEPEN, ResponseLength.MEDIUM),
    ("Keep it short.", "learning", StudentIntent.DEPTH_SHORT, TeachingMode.ACKNOWLEDGE, ConversationMove.SHORTEN, ResponseLength.MICRO),
    ("Give me a simpler example.", "learning", StudentIntent.DEPTH_SIMPLER, TeachingMode.CLARIFY, ConversationMove.GIVE_EXAMPLE, ResponseLength.MEDIUM),
]


def test_human_feel_utterance_suite():
    engine = TutorEngine()
    for utterance, phase, intent, mode, move, length in SUITE:
        state = TutorState(
            phase=phase,
            current_question_id="q1" if phase == "practice" else None,
            current_section_title="Euclidean Division Lemma",
        )
        decision = engine.decide(utterance, state)
        assert decision.intent == intent, f"{utterance!r} intent={decision.intent}"
        assert decision.mode == mode, f"{utterance!r} mode={decision.mode}"
        assert decision.move == move, f"{utterance!r} move={decision.move}"
        assert decision.response_length == length, f"{utterance!r} length={decision.response_length}"


def test_still_dont_get_it_changes_strategy():
    engine = TutorEngine()
    state = TutorState(phase="learning")
    first = engine.decide("I don't understand.", state)
    second = engine.decide("Still don't get it.", state)
    assert first.move == ConversationMove.SIMPLIFY
    assert second.move == ConversationMove.GIVE_EXAMPLE
    assert first.move != second.move


def test_what_is_b_does_not_overteach():
    engine = TutorEngine()
    state = TutorState(phase="learning")
    decision = engine.decide("What is b?", state)
    assert decision.move == ConversationMove.ANSWER_DIRECT
    assert "neighbouring" in decision.strategy.lower() or "do not explain" in decision.strategy.lower()
    assert decision.check_understanding is False
