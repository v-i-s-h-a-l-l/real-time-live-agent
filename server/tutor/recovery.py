"""Check-in / struggle / done-choice recovery overrides.

Moved out of policy.py with no logic changes. Ordinary hunger, movie, and
first-tangent routing stay in ConversationPolicy.select + routing.
"""

from __future__ import annotations

from typing import Any

from tutor.intent import (
    CheckInReason,
    classify_check_in_reason,
    is_dismissive,
    is_done_now,
    is_give_up,
    is_post_correction_frustration,
    is_ready_to_proceed,
)
from tutor.policy_common import (
    _continue_lesson,
    _with_correction_close,
    _with_loop_close,
)
from tutor.practice import AnswerEvaluation, PracticeSnapshot
from tutor.steer import NeedKind, SteerAction, classify_need, steer_note
from tutor.types import (
    ConversationMove,
    ResponseLength,
    StudentIntent,
    TeachingMode,
    TutorDecision,
    TutorState,
)


class RecoveryPolicy:
    def override(
        self,
        intent: StudentIntent,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None,
        practice: PracticeSnapshot | None,
    ) -> TutorDecision | None:
        """Follow-ups that only fire after a check-in or a failed re-engage.

        Ordinary hunger, movie, and first-tangent routing stay untouched.
        """
        del phase, tutor_context
        need = classify_need(utterance)
        if need in {NeedKind.PAUSE, NeedKind.LEAVE}:
            return None

        if state.awaiting_done_choice:
            if intent == StudentIntent.STUDENT_ANSWER:
                return None
            return self._after_done_choice(intent, state, utterance)
        struggle = self._struggle_recovery(intent, state, utterance, practice)
        if struggle is not None:
            return struggle
        if state.just_corrected and is_post_correction_frustration(utterance, intent):
            return self._after_correction_frustration(intent, state, utterance)
        if state.reengage_attempted and is_dismissive(utterance):
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.REDIRECT,
                move=ConversationMove.REDIRECT,
                response_length=ResponseLength.SHORT,
                strategy=(
                    "Chosen action: CONFIRM_DONE. They pushed you away after you already "
                    "tried to re-engage. Do not go silent and do not teach. "
                    "One short line only: ask whether they want to stop the session now, or "
                    "whether the last attempt still did not click. No pushback. Then wait."
                ),
                check_understanding=True,
                notes=("scope_lock", steer_note(SteerAction.CONFIRM_DONE)),
            )
        if state.awaiting_recovery_work:
            switched = self._reason_switch(intent, state, utterance)
            if switched is not None:
                return switched
        if state.awaiting_reason:
            if is_ready_to_proceed(utterance):
                return _continue_lesson(intent, phase=state.phase)
            return self._after_check_in(intent, state, utterance)
        return None

    def _struggle_recovery(
        self,
        intent: StudentIntent,
        state: TutorState,
        utterance: str,
        practice: PracticeSnapshot | None,
    ) -> TutorDecision | None:
        """Override normal pacing after repeated misses or explicit surrender."""
        evaluation = practice.evaluation if practice is not None else None
        if evaluation == AnswerEvaluation.CORRECT or intent == StudentIntent.SUCCESS:
            return None

        gave_up = is_give_up(utterance) or evaluation == AnswerEvaluation.NEEDS_HINT
        current_miss = evaluation in {
            AnswerEvaluation.INCORRECT,
            AnswerEvaluation.PARTIALLY_CORRECT,
        }
        repeated = bool(
            practice is not None
            and current_miss
            and (
                practice.attempt_number >= 2
                or practice.consecutive_struggles >= 2
            )
        )
        struggling_again = bool(
            state.struggle_pacing
            and (
                gave_up
                or current_miss
                or is_post_correction_frustration(utterance, intent)
            )
        )
        if not (gave_up or repeated or struggling_again):
            return None

        return TutorDecision(
            intent=intent,
            mode=TeachingMode.CLARIFY,
            move=ConversationMove.SIMPLIFY,
            response_length=ResponseLength.GUIDED,
            strategy=(
                "Strong struggle signal: explicit give-up language, two or more "
                "wrong/incomplete attempts, or renewed frustration while already "
                "in struggle pacing. This overrides normal pacing. "
                "FIRST acknowledge the struggle warmly in one short line and "
                "normalize getting stuck. Never skip that acknowledgment even if "
                "you already know the next step. "
                "THEN simplify further than before: use smaller numbers, fewer "
                "steps, or break the SAME problem into ONE smaller sub-step. "
                "Stop there and wait for their response. "
                "Do NOT give a full worked example. Do NOT introduce a fresh "
                "independent task. Do NOT combine an example and a new task in "
                "this message. Do NOT explain multiple steps. "
                "A fresh task is allowed only after they answer correctly or "
                "clearly re-engage."
            ),
            allow_reveal_answer=False,
            use_next_hint=bool(
                practice is not None
                and evaluation in {
                    AnswerEvaluation.INCORRECT,
                    AnswerEvaluation.PARTIALLY_CORRECT,
                    AnswerEvaluation.NEEDS_HINT,
                }
            ),
            check_understanding=True,
            notes=("multi_struggle", "soft_tone"),
            evaluation=evaluation.value if evaluation is not None else None,
            hint_level=practice.hint_level if practice is not None else 0,
        )

    def _reason_switch(
        self,
        intent: StudentIntent,
        state: TutorState,
        utterance: str,
    ) -> TutorDecision | None:
        """They named a new reason before trying the last recovery task."""
        reason = classify_check_in_reason(utterance)
        if reason not in {CheckInReason.BORED, CheckInReason.CONFUSED}:
            return None
        if reason == state.last_recovery:
            return None
        branched = self._after_check_in(intent, state, utterance)
        if branched is None:
            return None
        return _with_loop_close(branched)

    def _after_correction_frustration(
        self,
        intent: StudentIntent,
        state: TutorState,
        utterance: str,
    ) -> TutorDecision:
        """Wrong-answer correction, then heat: acknowledge, then ONE smaller sub-step."""
        del state, utterance
        return _with_correction_close(
            TutorDecision(
                intent=intent,
                mode=TeachingMode.CLARIFY,
                move=ConversationMove.SIMPLIFY,
                response_length=ResponseLength.GUIDED,
                strategy=(
                    "Do not re-teach the correction. After the opening beat, "
                    "give ONE smaller sub-step of the SAME problem — smaller "
                    "numbers, fewer moving parts, or breaking the step in "
                    "half. Do NOT introduce a brand-new word-problem. Do NOT "
                    "ask a fresh independent question. Do NOT combine a "
                    "worked example with a new task in this message. Stop "
                    "after the one smaller step and wait for their reply "
                    "before adding more."
                ),
                allow_reveal_answer=False,
                check_understanding=True,
                notes=("recovery_confused",),
            )
        )

    def _after_check_in(
        self,
        intent: StudentIntent,
        state: TutorState,
        utterance: str,
    ) -> TutorDecision | None:
        reason = classify_check_in_reason(utterance)
        if reason == CheckInReason.NONE:
            if is_ready_to_proceed(utterance):
                return _continue_lesson(intent, phase=state.phase)
            if intent in {
                StudentIntent.UNRELATED,
                StudentIntent.TOPIC_CHANGE,
            }:
                # Still a tangent — existing redirect / hold-firm logic applies.
                return None
            if intent in {
                StudentIntent.WHY_HOW,
                StudentIntent.EXPLANATION,
                StudentIntent.CLARIFICATION,
                StudentIntent.STUDENT_ANSWER,
                StudentIntent.HINT,
                StudentIntent.PRACTICE_REQUEST,
                StudentIntent.CONFUSION,
                StudentIntent.DISENGAGEMENT,
                StudentIntent.RELATED_EDUCATIONAL,
            }:
                return None
            # Short unmapped reply to our own question — clarify once.
            reason = CheckInReason.UNCLEAR
        if reason == CheckInReason.UNCLEAR:
            if is_ready_to_proceed(utterance):
                return _continue_lesson(intent, phase=state.phase)
            if state.check_in_clarified:
                return _continue_lesson(intent, phase=state.phase)
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.REDIRECT,
                move=ConversationMove.REDIRECT,
                response_length=ResponseLength.SHORT,
                strategy=(
                    "They answered your question, but the meaning is unclear. "
                    "Do not ignore it and do not change subject. "
                    "One short line: check whether they meant the topic is hard, "
                    "or something else. Then wait. Do not teach. Do not guess."
                ),
                check_understanding=True,
                notes=("scope_lock", "awaiting_reason", "clarify_once"),
            )
        if reason == CheckInReason.BORED:
            return TutorDecision(
                intent=StudentIntent.DISENGAGEMENT,
                mode=TeachingMode.SOCRATIC,
                move=ConversationMove.GUIDE,
                response_length=ResponseLength.GUIDED,
                strategy=(
                    "They said the topic is boring after you asked. Do NOT give another "
                    "worked example or explanation. Make this turn ACTIVE: one small "
                    "problem or quick challenge on the SAME concept for THEM to solve. "
                    "Hand it over and wait. End on that task, not on a demonstration."
                ),
                check_understanding=True,
                notes=("engagement", "recovery_bored"),
            )
        return TutorDecision(
            intent=StudentIntent.CONFUSION,
            mode=TeachingMode.CLARIFY,
            move=ConversationMove.SIMPLIFY,
            response_length=ResponseLength.GUIDED,
            strategy=(
                "They said the topic is confusing or hard after you asked. Slow down. "
                "Do not repeat the previous explanation at the same pace. "
                "Give ONE smaller first step, or a simpler example, or one guiding "
                "question that locates where they got lost. Then hand them one tiny "
                "thing they must try or answer. Wait. "
                "Do not re-ask a part they already established. If Latest student "
                "answer or Recent confusion focus names a solved piece (for example "
                "they already found q), keep that and target only the remaining gap."
            ),
            check_understanding=True,
            notes=("recovery_confused",),
        )

    def _after_done_choice(
        self,
        intent: StudentIntent,
        state: TutorState,
        utterance: str,
    ) -> TutorDecision:
        if is_done_now(utterance) or intent == StudentIntent.ACKNOWLEDGEMENT:
            return TutorDecision(
                intent=intent,
                mode=TeachingMode.REDIRECT,
                move=ConversationMove.REDIRECT,
                response_length=ResponseLength.SHORT,
                strategy=(
                    "Chosen action: GRANT_LEAVE. They confirmed they are done. "
                    "Let them go. Do not teach. Do not guilt them. Do not push back."
                ),
                notes=("scope_lock", steer_note(SteerAction.GRANT_LEAVE)),
            )
        reason = classify_check_in_reason(utterance)
        if reason == CheckInReason.BORED:
            return self._after_check_in(intent, state, utterance) or TutorDecision(
                intent=StudentIntent.DISENGAGEMENT,
                mode=TeachingMode.SOCRATIC,
                move=ConversationMove.GUIDE,
                response_length=ResponseLength.GUIDED,
                strategy=(
                    "The last re-engage did not land and they are bored. "
                    "One small challenge for them to try. No new lecture."
                ),
                check_understanding=True,
                notes=("engagement", "recovery_bored"),
            )
        # They said the last attempt did not click, or anything else that is
        # not a clear stop — slow down rather than leave.
        return TutorDecision(
            intent=StudentIntent.CONFUSION,
            mode=TeachingMode.CLARIFY,
            move=ConversationMove.SIMPLIFY,
            response_length=ResponseLength.GUIDED,
            strategy=(
                "The last re-engage did not click. Slow down. One smaller step "
                "or a guiding question to find where they are lost. Then one "
                "tiny thing they must try. Do not repeat the previous attempt."
            ),
            check_understanding=True,
            notes=("recovery_confused",),
        )
