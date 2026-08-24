"""Inject a per-turn Tutor Engine directive before each LLM call."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    LLMContextFrame,
    LLMRunFrame,
    OutputTransportMessageFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from processors.llm_context_text import _last_user_text
from processors.session_context import (
    SessionContextStore,
    _LEARNING_MARKER,
    _SESSION_MARKER,
    _learning_note,
    _system_note,
    conversational_learning_note,
    conversational_session_note,
    scoped_learning_note,
    scoped_session_note,
    upsert_context_system_note,
)
from protocol import SERVER_PRACTICE_PROGRESS
from tutor.engine import TutorEngine
from tutor.intent import is_interrupt_style
from tutor.prompts import TUTOR_TURN_MARKER, build_tutor_turn_directive
from tutor.steer import STEER_NOTE_PREFIX, SteerAction
from tutor.types import TutorState

# Steer actions where the reply is entirely about the *student's* state — the
# lesson identity has no place in the response. The persistent context notes
# are fully stripped.
_WITHHELD_STEER_ACTIONS: frozenset[str] = frozenset(
    {
        SteerAction.GRANT_PAUSE.value,
        SteerAction.CONFIRM_PAUSE.value,
        SteerAction.GRANT_LEAVE.value,
        SteerAction.JOKE_BEAT.value,
        SteerAction.CONFIRM_DONE.value,
    }
)

# Steer actions where the reply *needs* to name what we're on to hold the
# line. Formulas/visible content are stripped, but the topic anchor stays.
_SCOPED_STEER_ACTIONS: frozenset[str] = frozenset(
    {
        SteerAction.DEFER_LIGHT.value,
        SteerAction.FINISH_THEN_PAUSE.value,
        SteerAction.HOLD_FIRM.value,
        SteerAction.HOLD_SCOPE.value,
        SteerAction.CHECK_IN.value,
    }
)


class TutorTurnProcessor(FrameProcessor):
    """Build teaching strategy from active lesson context + utterance (no extra LLM)."""

    def __init__(
        self,
        store: SessionContextStore,
        llm_context: LLMContext,
        *,
        session_id: str = "-",
        engine: TutorEngine | None = None,
        state: TutorState | None = None,
        get_language: Callable[[], str] | None = None,
        get_script: Callable[[], str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._store = store
        self._llm_context = llm_context
        self._session_id = session_id
        self._engine = engine or TutorEngine()
        self._state = state or TutorState()
        if self._state.session_started_at is None:
            self._state.session_started_at = time.monotonic()
        # Reads the LanguageTracker's active language (single source of truth),
        # which the upstream tracker has already updated for this turn.
        self._get_language = get_language
        self._get_script = get_script
        self._last_turn_key = ""

    @property
    def state(self) -> TutorState:
        return self._state

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, (LLMContextFrame, LLMRunFrame)):
            event = self._apply_tutor_turn()
            if event is not None:
                # State mirror for the UI. Nothing downstream waits on it.
                await self.push_frame(
                    OutputTransportMessageFrame(message=event),
                    FrameDirection.DOWNSTREAM,
                )

        await self.push_frame(frame, direction)

    def _apply_tutor_turn(self) -> dict[str, Any] | None:
        self._state.sync_from_session_context(self._store.context)
        self._state.sync_from_learning_context(self._store.learning_context)

        utterance = _last_user_text(self._llm_context.get_messages())
        if not utterance:
            logger.info(
                "[LLM_TUTOR_CONTEXT] session={} skip=no_user_utterance has_learning={} section={}",
                self._session_id,
                bool(self._store.learning_context),
                (self._store.learning_context or {}).get("sectionTitle"),
            )
            return None

        turn_key = "|".join(
            (
                utterance,
                self._state.phase,
                self._state.current_question_id or "",
                self._state.current_section_id or "",
            )
        )
        if turn_key == self._last_turn_key:
            return None
        self._last_turn_key = turn_key

        decision = self._engine.decide(
            utterance,
            self._state,
            learning_context=self._store.learning_context,
            tutor_context=self._store.tutor_context,
        )
        practice = self._engine.practice_snapshot()
        active_language = self._get_language() if self._get_language else None
        reply_script = self._get_script() if self._get_script else None
        directive = build_tutor_turn_directive(
            decision=decision,
            state=self._state,
            learning_context=self._store.learning_context,
            tutor_context=self._store.tutor_context,
            utterance=utterance,
            practice=practice,
            active_language=active_language,
            reply_script=reply_script,
        )

        # A conversational turn (grant_pause, finish_then_pause, defer_light,
        # hold_firm, hold_scope, joke_beat, grant_leave) must not have the slide
        # identity within reach. If [LEARNING_CONTEXT] still names the topic
        # and lists formulas above, the model reliably tacks
        # "Let's stay on Euclid's Division Lemma" onto a reply that should just
        # let the student step away. Swap the persistent context notes for a
        # stripped placeholder for this one turn, and re-render the full notes
        # on the next teaching turn from what the store still holds.
        self._apply_context_scope(decision)

        # Last message before generation: the turn's language and teaching
        # instruction has to outrank the English-heavy history above it.
        upsert_context_system_note(
            self._llm_context, TUTOR_TURN_MARKER, directive, pin_to_end=True
        )
        _log_llm_tutor_context(
            session_id=self._session_id,
            state=self._state,
            learning_context=self._store.learning_context,
            messages=self._llm_context.get_messages(),
            intent=decision.intent.value,
            mode=decision.mode.value,
            move=decision.move.value,
            length=decision.response_length.value,
            interrupt=is_interrupt_style(utterance),
        )

        if self._state.phase != "practice" or practice.evaluation is None:
            return None
        logger.info(
            "[Practice] session={} question={} evaluation={} attempt={} hint_level={} mastery={}",
            self._session_id,
            practice.question_id,
            practice.evaluation.value,
            practice.attempt_number,
            practice.hint_level,
            practice.mastery.value,
        )
        return {"type": SERVER_PRACTICE_PROGRESS, **practice.to_payload()}


    def _apply_context_scope(self, decision) -> None:
        """Rewrite [LEARNING_CONTEXT]/[SESSION_CONTEXT] for the current turn.

        Three modes, one per turn:

        * WITHHELD — pure student-state (grant_pause / grant_leave / joke_beat):
          strip everything so no lesson identity leaks into a "go grab food"
          reply.
        * SCOPE-ONLY — scope-holding (hold_scope / hold_firm / defer_light /
          finish_then_pause): keep the topic and section name so the redirect
          can say "we're on Euclid's Division Lemma, that's later", but drop
          the slide text, formulas, and Next-step invitation so it does not
          also teach the concept.
        * FULL — teaching turns and resume_lesson: re-render the full notes
          straight from the client-supplied stores.
        """
        steer_action = None
        for note in decision.notes:
            if note.startswith(STEER_NOTE_PREFIX):
                steer_action = note[len(STEER_NOTE_PREFIX):]
                break

        if steer_action in _WITHHELD_STEER_ACTIONS:
            upsert_context_system_note(
                self._llm_context, _LEARNING_MARKER, conversational_learning_note()
            )
            upsert_context_system_note(
                self._llm_context, _SESSION_MARKER, conversational_session_note()
            )
            return

        if steer_action in _SCOPED_STEER_ACTIONS:
            learning_ctx = self._store.learning_context or {}
            session_ctx = self._store.context or {}
            upsert_context_system_note(
                self._llm_context, _LEARNING_MARKER, scoped_learning_note(learning_ctx)
            )
            upsert_context_system_note(
                self._llm_context, _SESSION_MARKER, scoped_session_note(session_ctx)
            )
            return

        if self._store.learning_context:
            upsert_context_system_note(
                self._llm_context, _LEARNING_MARKER, _learning_note(self._store.learning_context)
            )
        if self._store.context:
            upsert_context_system_note(
                self._llm_context, _SESSION_MARKER, _system_note(self._store.context)
            )


def _log_llm_tutor_context(
    *,
    session_id: str,
    state: TutorState,
    learning_context: dict[str, Any] | None,
    messages: list[dict[str, Any]],
    intent: str,
    mode: str,
    move: str,
    length: str,
    interrupt: bool,
) -> None:
    markers = []
    persona_lumina = False
    persona_ministros = False
    has_visible = False
    has_question = False
    if learning_context:
        has_visible = bool((learning_context.get("visibleContent") or "").strip())
        has_question = bool((learning_context.get("question") or "").strip())
    for msg in messages:
        if msg.get("role") != "system":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        if "Lumina" in content:
            persona_lumina = True
        if "Ministros" in content:
            persona_ministros = True
        for marker in ("[SESSION_CONTEXT]", "[LEARNING_CONTEXT]", "[TUTOR_TURN]"):
            if marker in content:
                markers.append(marker)
    logger.info(
        "[TUTOR_CONTEXT_CREATED] session={} topic={} section={} phase={} mode={} intent={} "
        "move={} length={} confusion={} hints={} depth={} interrupt={} practice={}",
        session_id,
        state.topic_id,
        state.current_section_id,
        state.phase,
        mode,
        intent,
        move,
        length,
        state.confusion_streak,
        state.hints_used,
        state.depth_preference,
        interrupt,
        state.phase == "practice",
    )
    logger.info(
        "[LLM_TUTOR_CONTEXT] session={} currentTopic={!r} currentSection={!r} hasVisibleContent={} hasPracticeQuestion={} markers={} persona_lumina={} persona_ministros={}",
        session_id,
        state.topic_title or state.topic_id,
        state.current_section_title or state.current_section_id,
        has_visible,
        has_question,
        markers,
        persona_lumina,
        persona_ministros,
    )
    if not learning_context:
        logger.warning(
            "[LLM_TUTOR_CONTEXT] session={} ACTIVE LEARNING CONTEXT MISSING — student slide is unknown",
            session_id,
        )
    if persona_ministros:
        logger.error(
            "[LLM_TUTOR_CONTEXT] session={} legacy Ministros persona still present in LLM messages",
            session_id,
        )
