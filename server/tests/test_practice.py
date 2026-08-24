"""Adaptive practice: evaluation contract, hint ladder, difficulty and mastery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tutor.engine import TutorEngine
from tutor.practice import (
    AnswerEvaluation,
    EvaluationResult,
    MasteryLevel,
    PracticeTracker,
    evaluate_answer,
    hint_for_level,
    normalize_answer,
)
from tutor.types import TeachingMode, TutorState

SHARED_CASES = (
    Path(__file__).resolve().parents[2] / "shared" / "practice-answer-cases.json"
)

TUTOR_CONTEXT = {
    "questionId": "q1",
    "expectedAnswer": "x = 2, 3",
    "acceptedAnswers": ["2 and 3"],
    "hints": [
        "Start by looking for two numbers whose product is 6.",
        "Those two numbers should also add up to 5.",
        "Try 2 and 3.",
    ],
    "solution": ["Factor as (x - 2)(x - 3).", "So the zeros are 2 and 3."],
}

LEARNING_CONTEXT = {
    "phase": "practice",
    "topicId": "zeros-coefficients",
    "questionId": "q1",
    "difficulty": "easy",
}


def _load_cases() -> list[dict]:
    return json.loads(SHARED_CASES.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["name"])
def test_shared_evaluation_contract(case: dict) -> None:
    """The frontend practice card runs the same table — keep both sides honest."""
    result = evaluate_answer(case["student"], case["expected"], case["accepted"])
    assert result.evaluation.value == case["evaluation"]


def test_normalization_is_notation_tolerant() -> None:
    assert normalize_answer("  X² × 2 ") == "x^2 * 2"
    assert normalize_answer("x = 3.") == "x = 3"


def test_partial_answer_reports_what_is_missing() -> None:
    result = evaluate_answer("x is 3", "x = 3, -3")
    assert result.evaluation == AnswerEvaluation.PARTIALLY_CORRECT
    assert result.missing_values == (-3.0,)


def test_hint_ladder_clamps_to_available_hints() -> None:
    hints = ["one", "two"]
    assert hint_for_level(hints, 0) is None
    assert hint_for_level(hints, 1) == "one"
    assert hint_for_level(hints, 2) == "two"
    assert hint_for_level(hints, 4) == "two"
    assert hint_for_level([], 2) is None


def _practice_engine() -> tuple[TutorEngine, TutorState]:
    engine = TutorEngine()
    state = TutorState(phase="practice", topic_id="zeros-coefficients", current_question_id="q1")
    state.sync_from_learning_context(LEARNING_CONTEXT)
    return engine, state


def _decide(engine: TutorEngine, state: TutorState, utterance: str):
    return engine.decide(
        utterance,
        state,
        learning_context=LEARNING_CONTEXT,
        tutor_context=TUTOR_CONTEXT,
    )


def test_correct_answer_is_confirmed_not_re_taught() -> None:
    engine, state = _practice_engine()
    decision = _decide(engine, state, "I think it's 2 and 3")
    assert decision.evaluation == AnswerEvaluation.CORRECT.value
    assert decision.allow_reveal_answer is False
    assert engine.practice.snapshot().correct == 1


def test_wrong_answers_walk_up_the_ladder_but_struggle_pacing_does_not_dump_solution() -> None:
    engine, state = _practice_engine()

    first = _decide(engine, state, "I think 2 and 4")
    assert first.evaluation == AnswerEvaluation.INCORRECT.value
    assert first.hint_level == 1
    assert first.allow_reveal_answer is False

    second = _decide(engine, state, "Maybe 2 and 5")
    assert second.hint_level == 2
    assert second.allow_reveal_answer is False

    third = _decide(engine, state, "Is it 1 and 6")
    assert third.hint_level == 3
    assert third.allow_reveal_answer is False

    fourth = _decide(engine, state, "Then 4 and 4")
    assert fourth.hint_level == 4
    # Multi-attempt struggle overrides the old full-solution dump: one smaller
    # sub-step and wait, even when the internal ladder reaches its final rung.
    assert fourth.allow_reveal_answer is False
    assert fourth.mode == TeachingMode.CLARIFY
    assert "multi_struggle" in fourth.notes


def test_hint_request_is_not_scored_as_a_wrong_answer() -> None:
    engine, state = _practice_engine()
    decision = _decide(engine, state, "Can you give me a hint?")
    assert decision.mode == TeachingMode.HINT
    assert decision.use_next_hint is True
    assert decision.evaluation == AnswerEvaluation.HINT_REQUEST.value
    snapshot = engine.practice.snapshot()
    assert snapshot.incorrect == 0
    assert snapshot.hints_used == 1


def test_dont_know_gets_a_hint_not_the_solution() -> None:
    engine, state = _practice_engine()
    decision = _decide(engine, state, "I don't know.")
    assert decision.evaluation == AnswerEvaluation.NEEDS_HINT.value
    assert decision.allow_reveal_answer is False
    assert decision.hint_level == 1
    assert engine.practice.snapshot().incorrect == 0


def test_conceptual_question_during_practice_is_not_an_attempt() -> None:
    engine, state = _practice_engine()
    decision = _decide(engine, state, "Why do we use this formula?")
    assert decision.evaluation is None
    assert engine.practice.snapshot().incorrect == 0


def test_clean_solve_earns_a_harder_question() -> None:
    tracker = PracticeTracker()
    tracker.sync_question("q1", topic_id="t1", difficulty="easy")
    tracker.record(EvaluationResult(AnswerEvaluation.CORRECT), "2 and 3")
    assert tracker.snapshot().recommended_difficulty == 2

    tracker.sync_question("q2", topic_id="t1", difficulty="medium")
    assert tracker.topic_progress("t1").current_difficulty == 2


def test_solving_with_hints_holds_difficulty() -> None:
    tracker = PracticeTracker()
    tracker.sync_question("q1", topic_id="t1", difficulty="medium")
    tracker.record(EvaluationResult(AnswerEvaluation.HINT_REQUEST), "hint please")
    tracker.record(EvaluationResult(AnswerEvaluation.CORRECT), "2 and 3")
    assert tracker.snapshot().recommended_difficulty == 2


def test_one_mistake_does_not_drop_difficulty() -> None:
    tracker = PracticeTracker()
    tracker.sync_question("q1", topic_id="t1", difficulty="hard")
    tracker.record(EvaluationResult(AnswerEvaluation.INCORRECT), "nope")
    assert tracker.snapshot().recommended_difficulty == 3

    tracker.record(EvaluationResult(AnswerEvaluation.INCORRECT), "still nope")
    assert tracker.snapshot().recommended_difficulty == 2


def test_difficulty_never_leaves_the_one_to_three_band() -> None:
    tracker = PracticeTracker()
    for index in range(6):
        question = f"q{index}"
        tracker.sync_question(question, topic_id="t1", difficulty="easy")
        tracker.record(EvaluationResult(AnswerEvaluation.CORRECT), "right")
    tracker.sync_question("q-last", topic_id="t1", difficulty="hard")
    assert tracker.topic_progress("t1").current_difficulty == 3


def test_mastery_climbs_with_independent_solves() -> None:
    tracker = PracticeTracker()
    assert tracker.snapshot().mastery == MasteryLevel.NOT_STARTED

    for index in range(3):
        tracker.sync_question(f"q{index}", topic_id="t1", difficulty="easy")
        tracker.record(EvaluationResult(AnswerEvaluation.CORRECT), "right")
    assert tracker.snapshot().mastery in {MasteryLevel.STRONG, MasteryLevel.MASTERED}


def test_mastery_stays_low_while_struggling() -> None:
    tracker = PracticeTracker()
    tracker.sync_question("q1", topic_id="t1", difficulty="medium")
    tracker.record(EvaluationResult(AnswerEvaluation.INCORRECT), "no")
    tracker.record(EvaluationResult(AnswerEvaluation.INCORRECT), "no")
    snapshot = tracker.snapshot()
    assert snapshot.mastery == MasteryLevel.LEARNING
    assert tracker.topic_progress("t1").needs_help is True


def test_moving_to_a_new_question_resets_per_question_counters() -> None:
    engine, state = _practice_engine()
    _decide(engine, state, "I think 2 and 4")
    assert engine.practice.snapshot().attempt_number == 1

    next_context = {**LEARNING_CONTEXT, "questionId": "q2", "difficulty": "medium"}
    state.sync_from_learning_context(next_context)
    engine.decide(
        "2 and 3",
        state,
        learning_context=next_context,
        tutor_context={**TUTOR_CONTEXT, "questionId": "q2"},
    )
    snapshot = engine.practice.snapshot()
    assert snapshot.question_id == "q2"
    assert snapshot.attempt_number == 1
    assert snapshot.hints_used == 0


def test_repeated_llm_frames_for_one_turn_count_once() -> None:
    engine, state = _practice_engine()
    _decide(engine, state, "I think 2 and 4")
    _decide(engine, state, "I think 2 and 4")
    snapshot = engine.practice.snapshot()
    assert snapshot.attempt_number == 1
    assert snapshot.incorrect == 1
    assert snapshot.hint_level == 1


def test_untrusted_accepted_answers_are_ignored() -> None:
    engine, state = _practice_engine()
    decision = engine.decide(
        "2 and 3",
        state,
        learning_context=LEARNING_CONTEXT,
        tutor_context={**TUTOR_CONTEXT, "acceptedAnswers": "not-a-list"},
    )
    assert decision.evaluation == AnswerEvaluation.CORRECT.value


def test_learning_phase_never_scores_answers() -> None:
    engine = TutorEngine()
    state = TutorState(phase="learning", topic_id="t1")
    decision = engine.decide("2 and 3", state, tutor_context=TUTOR_CONTEXT)
    assert decision.evaluation is None
    assert engine.practice.snapshot().evaluation is None


def test_progress_payload_is_ui_safe() -> None:
    engine, state = _practice_engine()
    _decide(engine, state, "I think it's 2 and 3")
    payload = engine.practice.snapshot().to_payload()
    assert payload["evaluation"] == "correct"
    assert payload["difficulty"] == "easy"
    assert payload["mastery"] in {level.value for level in MasteryLevel}
    # The mirror must never leak the answer key to the browser.
    serialized = json.dumps(payload)
    assert "expectedAnswer" not in serialized
    assert "2, 3" not in serialized
