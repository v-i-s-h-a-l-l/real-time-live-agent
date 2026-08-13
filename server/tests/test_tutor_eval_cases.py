"""Human-feel evaluation cases — deterministic intent/mode expectations (no live LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.engine import TutorEngine  # noqa: E402
from tutor.types import StudentIntent, TeachingMode, TutorState  # noqa: E402


CASES = [
    # CASE 1 — Basic explanation
    ("What is a quadratic equation?", "learning", StudentIntent.EXPLANATION, TeachingMode.LEARN),
    # CASE 2 — Confusion
    ("I don't understand.", "learning", StudentIntent.CONFUSION, TeachingMode.CLARIFY),
    # CASE 3 — Why question
    ("Why do we use the quadratic formula?", "learning", StudentIntent.WHY_HOW, TeachingMode.CLARIFY),
    # CASE 4 — Guided problem solving
    ("Solve this question.", "practice", StudentIntent.PRACTICE_REQUEST, TeachingMode.SOCRATIC),
    # CASE 5 — Wrong answer style
    ("I got 5.", "practice", StudentIntent.STUDENT_ANSWER, TeachingMode.EVALUATE),
    # CASE 6 — Hint
    ("Give me a hint.", "practice", StudentIntent.HINT, TeachingMode.HINT),
    # CASE 7 — Repeat
    ("Can you explain that again?", "learning", StudentIntent.REPEAT, TeachingMode.REPEAT),
    # CASE 8 — Related
    ("Where do we use this in real life?", "learning", StudentIntent.RELATED_EDUCATIONAL, TeachingMode.LEARN),
    # CASE 9 — Off-topic
    ("Who won the cricket match?", "learning", StudentIntent.UNRELATED, TeachingMode.REDIRECT),
    # CASE 10 — Short ack (must not lecture)
    ("Okay.", "learning", StudentIntent.ACKNOWLEDGEMENT, TeachingMode.ACKNOWLEDGE),
]


def test_human_feel_case_matrix():
    engine = TutorEngine()
    for utterance, phase, intent, mode in CASES:
        state = TutorState(phase=phase, current_question_id="q1" if phase == "practice" else None)
        decision = engine.decide(utterance, state)
        assert decision.intent == intent, f"{utterance!r} intent={decision.intent}"
        assert decision.mode == mode, f"{utterance!r} mode={decision.mode}"


def test_case4_guided_solving_not_reveal():
    """'Solve this' during practice should guide, not dump the answer."""
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    decision = engine.decide("Solve this question.", state)
    assert decision.allow_reveal_answer is False
    assert decision.mode == TeachingMode.SOCRATIC
    assert decision.intent == StudentIntent.PRACTICE_REQUEST


def test_case6_hint_not_solution():
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    decision = engine.decide("Give me a hint.", state)
    assert decision.allow_reveal_answer is False
    assert decision.use_next_hint is True


def test_case10_interruption_style_new_question():
    """After barge-in, engine only sees the new utterance — no prior incomplete reply."""
    engine = TutorEngine()
    state = TutorState(phase="learning", topic_title="Discriminant")
    decision = engine.decide("Wait, why did you use 5?", state)
    assert decision.intent == StudentIntent.WHY_HOW
    assert decision.mode == TeachingMode.CLARIFY


def test_answer_request_explicit_reveal():
    engine = TutorEngine()
    state = TutorState(phase="practice", current_question_id="q1")
    decision = engine.decide("Just give me the answer.", state)
    assert decision.allow_reveal_answer is True
