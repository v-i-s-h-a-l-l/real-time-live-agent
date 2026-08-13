"""Unit tests for Tutor Engine intent heuristics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.intent import detect_intent  # noqa: E402
from tutor.types import StudentIntent  # noqa: E402


def test_how_can_you_help():
    assert detect_intent("How can you help me?") == StudentIntent.EXPLANATION


def test_explanation_request():
    assert detect_intent("What is a quadratic equation?") == StudentIntent.EXPLANATION


def test_confusion():
    assert detect_intent("I don't understand.") == StudentIntent.CONFUSION


def test_why_how():
    assert detect_intent("Why do we use the quadratic formula?") == StudentIntent.WHY_HOW


def test_hint():
    assert detect_intent("Give me a hint.") == StudentIntent.HINT


def test_answer_request():
    assert detect_intent("Just tell me the answer.") == StudentIntent.ANSWER_REQUEST


def test_repeat():
    assert detect_intent("Can you explain that again?") == StudentIntent.REPEAT


def test_related_educational():
    assert (
        detect_intent("Where do we use this in real life?")
        == StudentIntent.RELATED_EDUCATIONAL
    )


def test_unrelated():
    assert detect_intent("Who won the cricket match?") == StudentIntent.UNRELATED


def test_student_answer_practice_short():
    assert (
        detect_intent("x is 2 and 3", phase="practice") == StudentIntent.STUDENT_ANSWER
    )


def test_student_answer_numeric():
    assert detect_intent("5", phase="practice") == StudentIntent.STUDENT_ANSWER


def test_acknowledgement():
    assert detect_intent("okay") == StudentIntent.ACKNOWLEDGEMENT


def test_hesitation_hmm():
    assert detect_intent("Hmm...") == StudentIntent.HESITATION


def test_success_i_get_it():
    assert detect_intent("Oh, I get it now.") == StudentIntent.SUCCESS


def test_weather_unrelated():
    assert detect_intent("What's the weather?") == StudentIntent.UNRELATED


def test_explain_more():
    assert detect_intent("Explain more.") == StudentIntent.DEPTH_MORE


def test_keep_it_short():
    assert detect_intent("Keep it short.") == StudentIntent.DEPTH_SHORT


def test_greeting():
    assert detect_intent("Hi there") == StudentIntent.GREETING


def test_practice_request():
    assert detect_intent("Can you give me another question?") == StudentIntent.PRACTICE_REQUEST
