"""TutorEngine — maps utterance + lesson context → teaching decision."""

from __future__ import annotations

from typing import Any

from loguru import logger

from tutor.faq import match_faq
from tutor.intent import detect_intent, is_interrupt_style
from tutor.policy import ConversationPolicy
from tutor.practice import (
    AnswerEvaluation,
    EvaluationResult,
    PracticeSnapshot,
    PracticeTracker,
    evaluate_answer,
)
from tutor.scope import APPLICATION_DOMAIN, apply_domain_scope
from tutor.types import StudentIntent, TutorDecision, TutorState

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

        self._update_state(state, decision, utterance)

        logger.info(
            "[TutorEngine] domain={} intent={} move={} length={} mode={} phase={} topic={} section={} "
            "question={} confusion={} hints={} depth={} off_topic={} reveal={} interrupt={} "
            "evaluation={} hint_level={} faq={}",
            APPLICATION_DOMAIN,
            decision.intent.value,
            decision.move.value,
            decision.response_length.value,
            decision.mode.value,
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
        return decision

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
        elif decision.intent == StudentIntent.DEPTH_SIMPLER:
            state.depth_preference = "beginner"

        if decision.intent == StudentIntent.UNRELATED:
            state.off_topic_count += 1

        if decision.intent == StudentIntent.STUDENT_ANSWER:
            state.last_student_answer = (utterance or "").strip()[:200]
        if decision.use_next_hint:
            state.hints_used += 1
