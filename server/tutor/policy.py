"""Conversation policy — what a good human tutor would do next (no extra LLM).

Thin coordinator: pause/leave → FAQ → recovery → adaptive practice → intent routing.
Domain logic lives in policy_common, policy_faq, policy_practice, depth, recovery, routing.
Helpers used by engine.py are re-exported here so call sites stay unchanged.
"""

from __future__ import annotations

from typing import Any, Callable

from tutor.faq import FAQEntry
from tutor.steer import NeedKind, classify_need
from tutor.practice import PracticeSnapshot
from tutor.policy_common import (
    _resume,
    _steer,
    _with_gap_ack,
    _with_hostility_boundary,
    _with_soft_tone,
)
from tutor.depth import apply_depth
from tutor.policy_faq import faq_decision
from tutor.policy_practice import adaptive_practice
from tutor.recovery import RecoveryPolicy
from tutor.routing import IntentRouter
from tutor.types import (
    StudentIntent,
    TutorDecision,
    TutorState,
)

_Handler = Callable[
    [StudentIntent, str, TutorState, str, dict[str, Any] | None],
    TutorDecision,
]


class ConversationPolicy:
    """Maps intent + compact tutor state to a teaching move.

    Does not generate the spoken reply. The main LLM still does that.
    """

    def __init__(self) -> None:
        self._recovery = RecoveryPolicy()
        self._router = IntentRouter()
        self._handlers: dict[StudentIntent, _Handler] = {
            StudentIntent.GREETING: self._router._greet,
            StudentIntent.UNRELATED: self._router._redirect,
            StudentIntent.RELATED_EDUCATIONAL: self._router._related,
            StudentIntent.HINT: self._router._hint,
            StudentIntent.ANSWER_REQUEST: self._router._answer_request,
            StudentIntent.CONFUSION: self._router._confusion,
            StudentIntent.REPEAT: self._router._repeat,
            StudentIntent.WHY_HOW: self._router._why_how,
            StudentIntent.STUDENT_ANSWER: self._router._student_answer,
            StudentIntent.PRACTICE_REQUEST: self._router._practice,
            StudentIntent.DISAGREEMENT: self._router._disagree,
            StudentIntent.ACKNOWLEDGEMENT: self._router._ack,
            StudentIntent.HESITATION: self._router._hesitate,
            StudentIntent.SUCCESS: self._router._success,
            StudentIntent.DEPTH_MORE: self._router._depth_more,
            StudentIntent.DEPTH_SHORT: self._router._depth_short,
            StudentIntent.DEPTH_SIMPLER: self._router._depth_simpler,
            StudentIntent.DISENGAGEMENT: self._router._disengage,
            StudentIntent.TOPIC_CHANGE: self._router._topic_change,
            StudentIntent.EXPLANATION: self._router._explain,
            StudentIntent.CLARIFICATION: self._router._explain,
        }

    def resume_from_pause(self, state: TutorState) -> TutorDecision:
        return _resume(state)

    def select(
        self,
        intent: StudentIntent,
        *,
        phase: str,
        state: TutorState,
        utterance: str,
        tutor_context: dict[str, Any] | None = None,
        practice: PracticeSnapshot | None = None,
        faq: FAQEntry | None = None,
    ) -> TutorDecision:
        # Priority 1: hunger, tiredness, breaks, leaving — never teach or quiz.
        need = classify_need(utterance)
        if need in {NeedKind.PAUSE, NeedKind.LEAVE}:
            steer_intent = (
                StudentIntent.UNRELATED
                if intent == StudentIntent.FAQ
                else intent
            )
            return self._finish(
                _steer(steer_intent, state, utterance, topic_shift=False),
                state,
            )
        if faq is not None:
            return self._finish(self._faq(faq), state)
        recovery = self._recovery_override(
            intent,
            phase,
            state,
            utterance,
            tutor_context,
            practice,
        )
        if recovery is not None:
            return self._finish(recovery, state)
        if practice is not None and phase == "practice":
            adaptive = self._adaptive_practice(intent, practice)
            if adaptive is not None:
                return self._finish(adaptive, state)
        handler = self._handlers.get(intent, self._router._default)
        return self._finish(handler(intent, phase, state, utterance, tutor_context), state)

    def _finish(self, decision: TutorDecision, state: TutorState) -> TutorDecision:
        decision = self._apply_depth(decision, state)
        if state.soft_tone_remaining > 0:
            return _with_soft_tone(decision)
        return decision

    def _recovery_override(
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
        return self._recovery.override(
            intent, phase, state, utterance, tutor_context, practice
        )

    def _adaptive_practice(
        self,
        intent: StudentIntent,
        practice: PracticeSnapshot,
    ) -> TutorDecision | None:
        """Teaching move for a scored practice turn. None = fall back to the generic path."""
        return adaptive_practice(intent, practice)

    def _faq(self, entry: FAQEntry) -> TutorDecision:
        return faq_decision(entry)

    def _apply_depth(self, decision: TutorDecision, state: TutorState) -> TutorDecision:
        return apply_depth(decision, state)
