"""Shared policy helpers used by routing, recovery, and the coordinator.

Moved out of policy.py with no logic changes. Re-exported from tutor.policy
so existing call sites (engine.py) keep the same import path.
"""

from __future__ import annotations

from tutor.intent import is_ready_to_proceed
from tutor.steer import SteerAction, resume_strategy, steer_note, steering_strategy
from tutor.types import (
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorDecision,
    TutorState,
)


def _continue_lesson(intent: StudentIntent, *, phase: str = "learning") -> TutorDecision:
    """Ready/neutral continue — never a diagnostic check-in."""
    resolved = (
        StudentIntent.EXPLANATION
        if intent in {StudentIntent.UNRELATED, StudentIntent.UNKNOWN, StudentIntent.ACKNOWLEDGEMENT}
        else intent
    )
    next_item = (
        "the next practice question, or the next concrete step of the current one"
        if phase == "practice"
        else "the current or next slide's actual content"
    )
    return TutorDecision(
        intent=resolved,
        mode=TeachingMode.LEARN,
        move=ConversationMove.EXPLAIN,
        response_length=ResponseLength.MEDIUM if phase == "practice" else ResponseLength.SHORT,
        strategy=(
            "They are ready to continue, or gave a neutral go-ahead. "
            "This is engagement, not struggle. Do NOT run a diagnostic "
            "check-in about how the topic feels. Pick up the current "
            "slide in one short spoken beat and move forward. "
            "Do NOT reply with only 'Okay.', 'Got it.', or 'let's proceed'. "
            f"This same turn MUST contain {next_item} — speak it now, "
            "the way you would if they asked you to explain it."
        ),
        check_understanding=False,
        notes=("ready_continue",),
    )


def _steer(
    intent: StudentIntent,
    state: TutorState,
    utterance: str,
    *,
    topic_shift: bool,
) -> TutorDecision:
    if is_ready_to_proceed(utterance):
        return _continue_lesson(intent, phase=state.phase)
    action, strategy = steering_strategy(
        state,
        utterance,
        consecutive=state.consecutive_drift,
        topic_shift=topic_shift,
    )
    check_in = action == SteerAction.CHECK_IN
    return TutorDecision(
        intent=intent,
        mode=TeachingMode.REDIRECT,
        move=ConversationMove.REDIRECT,
        response_length=ResponseLength.GUIDED if check_in else ResponseLength.SHORT,
        strategy=strategy,
        check_understanding=check_in,
        notes=("scope_lock", steer_note(action)),
    )


def _resume(state: TutorState) -> TutorDecision:
    return TutorDecision(
        intent=StudentIntent.ACKNOWLEDGEMENT,
        mode=TeachingMode.LEARN,
        move=ConversationMove.ACKNOWLEDGE,
        response_length=ResponseLength.SHORT,
        strategy=resume_strategy(state),
        check_understanding=False,
        notes=("scope_lock", steer_note(SteerAction.RESUME_LESSON)),
    )


def _with_loop_close(decision: TutorDecision) -> TutorDecision:
    """Keep the new approach; open with one beat about the unfinished attempt."""
    return TutorDecision(
        intent=decision.intent,
        mode=decision.mode,
        strategy=(
            "Close the loop on the last attempt before switching. Open with one "
            "short sentence that checks whether that previous example or task "
            "landed, then immediately continue into the new approach below — "
            "do not wait for an answer, do not add a second diagnostic question, "
            "and do not delay the switch. "
            + decision.strategy
        ),
        move=decision.move,
        response_length=ResponseLength.MEDIUM,
        allow_reveal_answer=decision.allow_reveal_answer,
        use_next_hint=decision.use_next_hint,
        check_understanding=decision.check_understanding,
        notes=decision.notes + ("loop_close",),
        evaluation=decision.evaluation,
        hint_level=decision.hint_level,
        faq_id=decision.faq_id,
        faq_answer=decision.faq_answer,
    )


def _with_correction_close(decision: TutorDecision) -> TutorDecision:
    """Correction plus frustration: acknowledge, then only one smaller sub-step."""
    return TutorDecision(
        intent=decision.intent,
        mode=decision.mode,
        strategy=(
            "A correction was just given and they reacted with frustration, "
            "give-up language, or disengagement. That is a signal the "
            "correction may not have landed, not only that the topic is dull. "
            "Open with ONE short sentence that normalizes getting a step wrong "
            "— warm, brief, not a lecture. Never skip that acknowledgment, "
            "even if a strong next step is ready. Then continue in the SAME "
            "reply with the plan below. Do not re-explain the correction. Do "
            "not wait for an answer to the acknowledgment. Warmer and more "
            "reassuring than a default redirect. "
            + decision.strategy
        ),
        move=decision.move,
        response_length=ResponseLength.GUIDED,
        allow_reveal_answer=decision.allow_reveal_answer,
        use_next_hint=decision.use_next_hint,
        check_understanding=decision.check_understanding,
        notes=decision.notes + ("loop_close", "correction_close", "soft_tone"),
        evaluation=decision.evaluation,
        hint_level=decision.hint_level,
        faq_id=decision.faq_id,
        faq_answer=decision.faq_answer,
    )


def _with_hostility_boundary(decision: TutorDecision) -> TutorDecision:
    """Hostility or profanity aimed at the tutor: prepend one calm boundary line."""
    return TutorDecision(
        intent=decision.intent,
        mode=decision.mode,
        strategy=(
            "The student directed hostility, profanity, or an insult AT YOU "
            "(the tutor), not just at the topic. Open with ONE short, calm, "
            "non-escalating boundary line, then still handle their actual "
            "request: briefly acknowledge their frustration, ask to keep it "
            "respectful, then continue with the plan below. Never dodge, skip, "
            "or refuse the actual ask after the boundary. Two sentences "
            "maximum for the boundary. Do NOT lecture, moralize, refuse to "
            "help, or be passive-aggressive. Model a calm boundary, not "
            "punishment. Then proceed. "
            + decision.strategy
        ),
        move=decision.move,
        response_length=decision.response_length,
        allow_reveal_answer=decision.allow_reveal_answer,
        use_next_hint=decision.use_next_hint,
        check_understanding=decision.check_understanding,
        notes=decision.notes
        + tuple(n for n in ("hostility_boundary", "soft_tone") if n not in decision.notes),
        evaluation=decision.evaluation,
        hint_level=decision.hint_level,
        faq_id=decision.faq_id,
        faq_answer=decision.faq_answer,
    )


def _with_gap_ack(decision: TutorDecision) -> TutorDecision:
    """A prior turn looks skipped or unanswered — acknowledge, then proceed."""
    return TutorDecision(
        intent=decision.intent,
        mode=decision.mode,
        strategy=(
            "A prior turn appears skipped, missing, or unanswered. Open with "
            "ONE short line that acknowledges the gap, then immediately "
            "answer their actual question or continue with the plan below. "
            "Do not pretend it did not happen. Do not dwell. "
            + decision.strategy
        ),
        move=decision.move,
        response_length=decision.response_length,
        allow_reveal_answer=decision.allow_reveal_answer,
        use_next_hint=decision.use_next_hint,
        check_understanding=decision.check_understanding,
        notes=decision.notes
        + tuple(n for n in ("gap_ack",) if n not in decision.notes),
        evaluation=decision.evaluation,
        hint_level=decision.hint_level,
        faq_id=decision.faq_id,
        faq_answer=decision.faq_answer,
    )


def _with_soft_tone(decision: TutorDecision) -> TutorDecision:
    if "soft_tone" in decision.notes or "scope_lock" in decision.notes:
        return decision
    return TutorDecision(
        intent=decision.intent,
        mode=decision.mode,
        strategy=decision.strategy,
        move=decision.move,
        response_length=decision.response_length,
        allow_reveal_answer=decision.allow_reveal_answer,
        use_next_hint=decision.use_next_hint,
        check_understanding=decision.check_understanding,
        notes=decision.notes + ("soft_tone",),
        evaluation=decision.evaluation,
        hint_level=decision.hint_level,
        faq_id=decision.faq_id,
        faq_answer=decision.faq_answer,
    )
