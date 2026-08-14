"""Inject a per-turn Tutor Engine directive before each LLM call."""

from __future__ import annotations

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

from processors.session_context import SessionContextStore, upsert_context_system_note
from protocol import SERVER_PRACTICE_PROGRESS
from tutor.engine import TutorEngine
from tutor.intent import is_interrupt_style
from tutor.prompts import TUTOR_TURN_MARKER, build_tutor_turn_directive
from tutor.types import TutorState


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
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._store = store
        self._llm_context = llm_context
        self._session_id = session_id
        self._engine = engine or TutorEngine()
        self._state = state or TutorState()
        # Reads the LanguageTracker's active language (single source of truth),
        # which the upstream tracker has already updated for this turn.
        self._get_language = get_language
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
        directive = build_tutor_turn_directive(
            decision=decision,
            state=self._state,
            learning_context=self._store.learning_context,
            tutor_context=self._store.tutor_context,
            utterance=utterance,
            practice=practice,
            active_language=active_language,
        )
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


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            text = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )
        else:
            text = str(content or "")
        text = text.strip()
        if text:
            return text
    return ""


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
