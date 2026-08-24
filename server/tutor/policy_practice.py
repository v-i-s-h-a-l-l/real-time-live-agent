"""Practice-turn teaching moves (hint ladder + scored-answer builders).

Moved out of policy.py with no logic changes. Existing tutor.practice remains
the evaluator; this module only maps a scored snapshot to a TutorDecision.
"""

from __future__ import annotations

from typing import Callable

from tutor.practice import MAX_HINT_LEVEL, AnswerEvaluation, PracticeSnapshot
from tutor.types import (
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorDecision,
)

_PracticeBuilder = Callable[[StudentIntent, PracticeSnapshot], TutorDecision]

#: What each rung of the hint ladder is allowed to give away.
_HINT_LADDER: dict[int, str] = {
    1: "Give one small conceptual nudge — the idea to look at, not the numbers.",
    2: "Give a more specific hint that narrows the search, still not the answer.",
    3: "Walk them through the next single step, then hand it back to them.",
    MAX_HINT_LEVEL: (
        "They have struggled enough. Say you'll work it through together, show the "
        "reasoning in a couple of spoken steps, and end with the answer."
    ),
}


def _ladder_rung(level: int) -> str:
    return _HINT_LADDER.get(max(1, min(MAX_HINT_LEVEL, level)), _HINT_LADDER[1])


def _correct(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    harder = practice.recommended_difficulty > practice.difficulty
    follow_up = (
        " Then offer one that is a little harder — one short sentence, not a speech."
        if harder
        else " Then move them on without ceremony."
    )
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.EVALUATE,
        move=ConversationMove.CELEBRATE,
        response_length=ResponseLength.SHORT,
        strategy=(
            "They got it right. Confirm it warmly and briefly the way a person would "
            "('Exactly.', 'That's it.') and restate the answer once. "
            "Vary the praise — never repeat a stock phrase you already used this session."
            + follow_up
            + " Do not re-teach the method and do not list the steps."
        ),
        allow_reveal_answer=False,
        check_understanding=False,
        evaluation=AnswerEvaluation.CORRECT.value,
    )


def _partially_correct(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.EVALUATE,
        move=ConversationMove.GUIDE,
        response_length=ResponseLength.GUIDED,
        strategy=(
            "Their reasoning is on the right track but the answer is incomplete. "
            "Say what they got right first, then point at the exact piece that is missing "
            "and ask one short question that gets them there. "
            "Do not say 'incorrect' and do not finish it for them."
        ),
        allow_reveal_answer=False,
        use_next_hint=practice.hint_level >= 1,
        check_understanding=False,
        evaluation=AnswerEvaluation.PARTIALLY_CORRECT.value,
        hint_level=practice.hint_level,
    )


def _incorrect(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    level = max(1, practice.hint_level)
    final = level >= MAX_HINT_LEVEL
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.CORRECT if final else TeachingMode.SOCRATIC,
        move=ConversationMove.ANSWER_DIRECT if final else ConversationMove.HINT,
        response_length=ResponseLength.MEDIUM if final else ResponseLength.GUIDED,
        strategy=(
            "That attempt is not right, but never say 'incorrect' or 'wrong'. "
            "Name the likely slip in their thinking in a few words. "
            + _ladder_rung(level)
            + (" Then wait for them." if not final else "")
        ),
        allow_reveal_answer=final,
        use_next_hint=not final,
        check_understanding=False,
        evaluation=AnswerEvaluation.INCORRECT.value,
        hint_level=level,
    )


def _needs_hint(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    level = max(1, practice.hint_level)
    final = level >= MAX_HINT_LEVEL
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.CORRECT if final else TeachingMode.HINT,
        move=ConversationMove.ANSWER_DIRECT if final else ConversationMove.HINT,
        response_length=ResponseLength.MEDIUM if final else ResponseLength.GUIDED,
        strategy=(
            "They said they don't know. Take the pressure off in a few words of your own. "
            + _ladder_rung(level)
            + (" Then wait for them." if not final else "")
        ),
        allow_reveal_answer=final,
        use_next_hint=not final,
        check_understanding=False,
        evaluation=AnswerEvaluation.NEEDS_HINT.value,
        hint_level=level,
    )


def _hint_request(intent: StudentIntent, practice: PracticeSnapshot) -> TutorDecision:
    level = max(1, practice.hint_level)
    final = level >= MAX_HINT_LEVEL
    return TutorDecision(
        intent=StudentIntent.HINT,
        mode=TeachingMode.CORRECT if final else TeachingMode.HINT,
        move=ConversationMove.ANSWER_DIRECT if final else ConversationMove.HINT,
        response_length=ResponseLength.SHORT if not final else ResponseLength.MEDIUM,
        strategy=(
            "They asked for a hint, so this is not a wrong answer. "
            + _ladder_rung(level)
            + (" Then wait." if not final else "")
        ),
        allow_reveal_answer=final,
        use_next_hint=not final,
        check_understanding=False,
        evaluation=AnswerEvaluation.HINT_REQUEST.value,
        hint_level=level,
    )


_PRACTICE_BUILDERS: dict[AnswerEvaluation, _PracticeBuilder] = {
    AnswerEvaluation.CORRECT: _correct,
    AnswerEvaluation.PARTIALLY_CORRECT: _partially_correct,
    AnswerEvaluation.INCORRECT: _incorrect,
    AnswerEvaluation.NEEDS_HINT: _needs_hint,
    AnswerEvaluation.HINT_REQUEST: _hint_request,
}


def adaptive_practice(
    intent: StudentIntent,
    practice: PracticeSnapshot,
) -> TutorDecision | None:
    """Teaching move for a scored practice turn. None = fall back to the generic path."""
    evaluation = practice.evaluation
    if evaluation is None:
        return None
    builder = _PRACTICE_BUILDERS.get(evaluation)
    if builder is None:
        return None
    return builder(intent, practice)
