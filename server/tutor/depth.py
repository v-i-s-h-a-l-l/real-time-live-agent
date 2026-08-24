"""Post-decision depth overlay (session preference: short / deep / beginner).

Moved out of policy.py with no logic changes. DEPTH_* intent handlers stay
in routing; this module only adjusts length/notes after a move is chosen.
"""

from __future__ import annotations

from tutor.types import (
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TutorDecision,
    TutorState,
)


def apply_depth(decision: TutorDecision, state: TutorState) -> TutorDecision:
    if decision.intent == StudentIntent.FAQ:
        return decision
    pref = state.depth_preference
    if decision.response_length == ResponseLength.MICRO:
        return decision
    extra: list[str] = list(decision.notes)
    length = decision.response_length
    if pref == "short" and length in {ResponseLength.MEDIUM, ResponseLength.GUIDED}:
        length = ResponseLength.SHORT
        extra.append("They asked to keep it short.")
    elif pref == "deep" and length == ResponseLength.SHORT and decision.move in {
        ConversationMove.EXPLAIN,
        ConversationMove.DEEPEN,
        ConversationMove.SIMPLIFY,
    }:
        length = ResponseLength.MEDIUM
        extra.append("They asked for more depth earlier.")
    elif pref == "beginner":
        extra.append("Explain like a beginner — simpler words, one idea at a time.")
    if extra == list(decision.notes) and length == decision.response_length:
        return decision
    return TutorDecision(
        intent=decision.intent,
        mode=decision.mode,
        strategy=decision.strategy,
        move=decision.move,
        response_length=length,
        allow_reveal_answer=decision.allow_reveal_answer,
        use_next_hint=decision.use_next_hint,
        check_understanding=decision.check_understanding,
        notes=tuple(extra),
        evaluation=decision.evaluation,
        hint_level=decision.hint_level,
        faq_id=decision.faq_id,
        faq_answer=decision.faq_answer,
    )
