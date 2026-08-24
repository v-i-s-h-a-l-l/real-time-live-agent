"""TutorEngine — maps utterance + lesson context → teaching decision."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from loguru import logger

import config
from ops_log import ops_event
from tutor.faq import match_faq
from tutor.intent import (
    CheckInReason,
    classify_check_in_reason,
    detect_intent,
    is_dismissive,
    is_done_now,
    is_hostile_to_tutor,
    is_interrupt_style,
    is_missed_turn,
    is_ready_to_proceed,
)
from tutor.policy import ConversationPolicy, _with_gap_ack, _with_hostility_boundary
from tutor.practice import (
    AnswerEvaluation,
    EvaluationResult,
    PracticeSnapshot,
    PracticeTracker,
    evaluate_answer,
)
from tutor.scope import APPLICATION_DOMAIN, apply_domain_scope
from tutor.steer import (
    PAUSE_GRANT_ACTIONS,
    SCOPE_HOLD_ACTIONS,
    STEER_NOTE_PREFIX,
    NeedKind,
    SteerAction,
    classify_need,
    is_break_negotiation,
    is_pause_meta_talk,
    is_return_utterance,
)

_SCOPE_HOLD_VALUES = frozenset(action.value for action in SCOPE_HOLD_ACTIONS)
from tutor.types import (
    ConversationMove,
    StudentIntent,
    TeachingMode,
    TutorDecision,
    TutorState,
)

# Acknowledgements and hesitation must not wipe a confusion streak.
_KEEP_CONFUSION = {
    StudentIntent.ACKNOWLEDGEMENT,
    StudentIntent.HESITATION,
    StudentIntent.REPEAT,
    StudentIntent.HINT,
    StudentIntent.WHY_HOW,
    StudentIntent.DEPTH_MORE,
    StudentIntent.DEPTH_SHORT,
    StudentIntent.DEPTH_SIMPLER,
    StudentIntent.CONFUSION,
    StudentIntent.UNRELATED,
    StudentIntent.DISENGAGEMENT,
    StudentIntent.TOPIC_CHANGE,
    StudentIntent.RELATED_EDUCATIONAL,
}


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _text_list(value: Any) -> tuple[str, ...]:
    """Browser-supplied payload: anything that is not a list of strings is ignored."""
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


class TutorEngine:
    """Deterministic teaching-policy layer. Language understanding stays with the LLM."""

    def __init__(
        self,
        policy: ConversationPolicy | None = None,
        practice: PracticeTracker | None = None,
    ) -> None:
        self._policy = policy or ConversationPolicy()
        self._practice = practice or PracticeTracker()

    @property
    def practice(self) -> PracticeTracker:
        """Adaptive practice state for this session — the source of truth for attempts."""
        return self._practice

    def practice_snapshot(self) -> PracticeSnapshot:
        return self._practice.snapshot()

    def decide(
        self,
        utterance: str,
        state: TutorState,
        *,
        learning_context: dict[str, Any] | None = None,
        tutor_context: dict[str, Any] | None = None,
    ) -> TutorDecision:
        phase = state.phase or "learning"
        if learning_context and learning_context.get("phase"):
            phase = str(learning_context["phase"])

        hostile = is_hostile_to_tutor(utterance)
        self._maybe_expire_awaiting(state, utterance)

        if state.awaiting_return and is_return_utterance(utterance):
            decision = self._policy.resume_from_pause(state)
            if is_missed_turn(utterance):
                decision = _with_gap_ack(decision)
            if hostile:
                decision = _with_hostility_boundary(decision)
            self._update_state(state, decision, utterance)
            self._log_decision(decision, state, phase, utterance)
            return decision

        intent = detect_intent(utterance, phase=phase)
        faq = match_faq(utterance)
        if faq is not None:
            intent = StudentIntent.FAQ
        intent = apply_domain_scope(intent, utterance, state)
        if intent != StudentIntent.FAQ:
            faq = None
        practice = self._track_practice(
            intent,
            phase=phase,
            state=state,
            utterance=utterance,
            learning_context=learning_context,
            tutor_context=tutor_context,
        )
        decision = self._policy.select(
            intent,
            phase=phase,
            state=state,
            utterance=utterance,
            tutor_context=tutor_context,
            practice=practice,
            faq=faq,
        )

        if is_missed_turn(utterance):
            decision = _with_gap_ack(decision)
        if hostile:
            decision = _with_hostility_boundary(decision)

        self._update_state(state, decision, utterance)
        self._log_decision(decision, state, phase, utterance)
        return decision

    def _log_decision(
        self,
        decision: TutorDecision,
        state: TutorState,
        phase: str,
        utterance: str,
    ) -> None:
        steer = next(
            (note.split(":", 1)[1] for note in decision.notes if note.startswith("steer:")),
            "-",
        )
        logger.info(
            "[TutorEngine] domain={} intent={} move={} length={} mode={} steer={} phase={} topic={} section={} "
            "question={} confusion={} hints={} depth={} off_topic={} reveal={} interrupt={} "
            "evaluation={} hint_level={} faq={}",
            APPLICATION_DOMAIN,
            decision.intent.value,
            decision.move.value,
            decision.response_length.value,
            decision.mode.value,
            steer,
            phase,
            state.topic_id,
            state.current_section_id,
            state.current_question_id,
            state.confusion_streak,
            state.hints_used,
            state.depth_preference,
            state.off_topic_count,
            decision.allow_reveal_answer,
            is_interrupt_style(utterance),
            decision.evaluation,
            decision.hint_level,
            decision.faq_id,
        )

    def _track_practice(
        self,
        intent: StudentIntent,
        *,
        phase: str,
        state: TutorState,
        utterance: str,
        learning_context: dict[str, Any] | None,
        tutor_context: dict[str, Any] | None,
    ) -> PracticeSnapshot | None:
        """Fold this turn into adaptive practice state. Deterministic, no LLM, no I/O."""
        if phase != "practice":
            return None

        context = learning_context or {}
        tutor = tutor_context or {}
        self._practice.sync_question(
            _text(context.get("questionId")) or state.current_question_id,
            topic_id=_text(context.get("topicId")) or state.topic_id,
            difficulty=context.get("difficulty"),
        )

        scored = intent in (StudentIntent.HINT, StudentIntent.STUDENT_ANSWER)
        if scored and self._practice.already_recorded(utterance):
            # Same student turn, second LLM frame: keep the verdict, don't re-count it.
            return self._practice.snapshot()

        if intent == StudentIntent.HINT:
            self._practice.record(EvaluationResult(AnswerEvaluation.HINT_REQUEST), utterance)
        elif intent == StudentIntent.STUDENT_ANSWER:
            self._practice.record(
                evaluate_answer(
                    utterance,
                    _text(tutor.get("expectedAnswer")),
                    _text_list(tutor.get("acceptedAnswers")),
                ),
                utterance,
            )
        else:
            self._practice.clear_turn()

        return self._practice.snapshot()

    def _update_state(self, state: TutorState, decision: TutorDecision, utterance: str) -> None:
        state.last_intent = decision.intent
        state.teaching_mode = decision.mode
        state.last_move = decision.move

        if decision.intent == StudentIntent.CONFUSION:
            state.confusion_streak += 1
            focus = (utterance or "").strip()[:160]
            if focus:
                state.last_confusion_focus = focus
        elif decision.intent not in _KEEP_CONFUSION:
            state.confusion_streak = 0
            if decision.intent == StudentIntent.SUCCESS:
                state.last_confusion_focus = None

        if decision.intent == StudentIntent.DEPTH_MORE:
            state.depth_preference = "deep"
        elif decision.intent == StudentIntent.DEPTH_SHORT:
            state.depth_preference = "short"
        elif decision.intent == StudentIntent.DISENGAGEMENT:
            # Boredom is not a request for fewer words. Marking it "short" made
            # every later turn compress the same definition, which is exactly
            # what bored them. Aim for concrete and simple instead.
            state.depth_preference = "beginner"
        elif decision.intent == StudentIntent.DEPTH_SIMPLER:
            state.depth_preference = "beginner"

        steer = next(
            (note[len(STEER_NOTE_PREFIX) :] for note in decision.notes if note.startswith(STEER_NOTE_PREFIX)),
            None,
        )

        if decision.intent in {StudentIntent.UNRELATED, StudentIntent.TOPIC_CHANGE}:
            # A granted rest need is not an attempt to dodge the lesson, so it must
            # not spend a strike — otherwise saying "I'm hungry" makes the tutor
            # treat the next ordinary drift as a repeat offence and answer it firmly.
            if steer not in PAUSE_GRANT_ACTIONS:
                state.off_topic_count += 1

        state.student_turns += 1

        if decision.intent == StudentIntent.STUDENT_ANSWER:
            state.last_student_answer = (utterance or "").strip()[:200]
        if decision.use_next_hint:
            state.hints_used += 1

        if steer:
            state.last_steer_action = steer
            state.last_need_kind = classify_need(utterance).value
            state.awaiting_return = steer in PAUSE_GRANT_ACTIONS
            if steer in PAUSE_GRANT_ACTIONS or steer == SteerAction.RESUME_LESSON.value:
                state.consecutive_drift = 0
            elif steer in _SCOPE_HOLD_VALUES:
                state.consecutive_drift += 1
            else:
                state.consecutive_drift = 0
        elif decision.intent in {
            StudentIntent.EXPLANATION,
            StudentIntent.CLARIFICATION,
            StudentIntent.HINT,
            StudentIntent.STUDENT_ANSWER,
            StudentIntent.PRACTICE_REQUEST,
            StudentIntent.DISAGREEMENT,
            StudentIntent.SUCCESS,
            StudentIntent.FAQ,
            StudentIntent.REPEAT,
            StudentIntent.WHY_HOW,
            StudentIntent.DISENGAGEMENT,
            StudentIntent.CONFUSION,
            StudentIntent.ACKNOWLEDGEMENT,
        }:
            state.awaiting_return = False
            state.last_steer_action = None
            state.last_need_kind = None
            state.consecutive_drift = 0

        self._update_recovery(state, decision, utterance, steer)
        self._sync_awaiting_timer(state)

    def _awaiting_is_progress(self, state: TutorState, utterance: str) -> bool:
        """True when this turn is still addressing the pending awaiting_* question."""
        if is_pause_meta_talk(utterance):
            return False
        if is_return_utterance(utterance) or is_break_negotiation(utterance):
            return True
        need = classify_need(utterance)
        if need in {NeedKind.PAUSE, NeedKind.LEAVE}:
            return True
        if classify_check_in_reason(utterance) != CheckInReason.NONE:
            return True
        if is_ready_to_proceed(utterance) or is_dismissive(utterance) or is_done_now(utterance):
            return True
        return False

    def _log_awaiting_escape(self, utterance: str, *, reason: str) -> None:
        ops_event(
            "awaiting_escaped",
            category="tutor",
            utterance_hash=hashlib.sha256(utterance.encode("utf-8")).hexdigest(),
            reason=reason,
        )

    def _maybe_expire_awaiting(self, state: TutorState, utterance: str) -> None:
        if not state.any_awaiting():
            return
        if self._awaiting_is_progress(state, utterance):
            state.awaiting_misses = 0
            return
        now = time.monotonic()
        if (
            state.awaiting_since_at is not None
            and (now - state.awaiting_since_at) >= config.AWAITING_TIMEOUT_SECS
        ):
            self._log_awaiting_escape(utterance, reason="timeout")
            state.clear_awaiting()
            return
        state.awaiting_misses += 1
        if state.awaiting_misses >= config.AWAITING_MISS_RESUME_AFTER:
            self._log_awaiting_escape(utterance, reason="miss_budget")
            state.clear_awaiting()

    def _sync_awaiting_timer(self, state: TutorState) -> None:
        if state.any_awaiting():
            if state.awaiting_since_at is None:
                state.awaiting_since_at = time.monotonic()
            return
        state.awaiting_misses = 0
        state.awaiting_since_at = None

    def _update_recovery(
        self,
        state: TutorState,
        decision: TutorDecision,
        utterance: str,
        steer: str | None,
    ) -> None:
        """Lightweight session memory for recovery tone and follow-ups."""
        notes = set(decision.notes)
        state.just_corrected = (
            decision.evaluation in {"incorrect", "partially_correct"}
            or decision.move == ConversationMove.CORRECT
            or decision.mode == TeachingMode.CORRECT
        )
        if steer in PAUSE_GRANT_ACTIONS:
            state.session_signals = _add_signal(state, "physical_need")
            state.soft_tone_remaining = max(state.soft_tone_remaining, 2)
        if decision.intent == StudentIntent.DISENGAGEMENT:
            state.session_signals = _add_signal(state, "bored")
        if decision.intent == StudentIntent.CONFUSION:
            state.session_signals = _add_signal(state, "confused")
        if state.consecutive_drift >= 2 or state.off_topic_count >= 2:
            state.soft_tone_remaining = max(state.soft_tone_remaining, 2)
        if "soft_tone" in notes:
            state.soft_tone_remaining = max(0, state.soft_tone_remaining - 1)

        if steer == SteerAction.CHECK_IN.value or "awaiting_reason" in notes:
            state.awaiting_reason = True
            state.awaiting_done_choice = False
            state.check_in_asked = True
            if "clarify_once" in notes:
                state.check_in_clarified = True
            return
        if steer == SteerAction.CONFIRM_DONE.value:
            state.awaiting_done_choice = True
            state.awaiting_reason = False
            return

        if "multi_struggle" in notes:
            state.session_signals = _add_signal(state, "struggling")
            state.soft_tone_remaining = max(state.soft_tone_remaining, 2)
            state.struggle_pacing = True
            state.reengage_attempted = True
            state.awaiting_reason = False
            state.awaiting_done_choice = False
            state.awaiting_recovery_work = True
            state.last_recovery = "confused"
            return

        if "recovery_bored" in notes or "recovery_confused" in notes or "engagement" in notes:
            state.reengage_attempted = True
            state.awaiting_reason = False
            state.awaiting_done_choice = False
            state.awaiting_recovery_work = True
            if "correction_close" in notes:
                state.struggle_pacing = True
                state.session_signals = _add_signal(state, "struggling")
            state.last_recovery = (
                "confused" if "recovery_confused" in notes else "bored"
            )
            return

        if decision.intent in {
            StudentIntent.STUDENT_ANSWER,
            StudentIntent.SUCCESS,
            StudentIntent.WHY_HOW,
            StudentIntent.EXPLANATION,
            StudentIntent.ACKNOWLEDGEMENT,
        }:
            state.reengage_attempted = False
            state.awaiting_reason = False
            state.awaiting_done_choice = False
            state.awaiting_recovery_work = False
            state.struggle_pacing = False
            state.check_in_asked = False
            state.check_in_clarified = False
        elif steer in PAUSE_GRANT_ACTIONS or steer == SteerAction.RESUME_LESSON.value:
            state.awaiting_reason = False
            state.awaiting_done_choice = False
            state.check_in_asked = False
            state.check_in_clarified = False
            if steer == SteerAction.RESUME_LESSON.value:
                state.reengage_attempted = False


def _add_signal(state: TutorState, signal: str) -> tuple[str, ...]:
    if signal in state.session_signals:
        return state.session_signals
    return state.session_signals + (signal,)
