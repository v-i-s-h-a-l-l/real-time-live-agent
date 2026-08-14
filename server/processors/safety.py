"""Safety-turn interceptor.

Sits after typed `text_input` and the user aggregator, before study-break and
the Tutor Engine. Voice and typed turns both arrive as LLMContextFrame, so
one processor covers both.

Audio, VAD, STT, TTS, and interruption are untouched. Ordinary tutoring is
not sent through an extra LLM: a miss is a regex no-op and the frame is
pushed through unchanged.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    LLMContextFrame,
    LLMMessagesAppendFrame,
    LLMRunFrame,
    OutputTransportMessageFrame,
    StopFrame,
    TTSSpeakFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from languages import LANG_EN
from processors.session_context import SessionContextStore, upsert_context_system_note
from tutor.safety import (
    SAFETY_CONTEXT_MARKER,
    SAFETY_CONTEXT_NOTE,
    SafetyStore,
    SafetyTurnResult,
)

# Voice turns arrive as LLMMessagesAppendFrame (+ LLMRunFrame). Typed chat
# uses LLMContextFrame. TutorTurnProcessor listens to all three; we must too
# or the math LLM still answers.
_LLM_TURN_FRAMES = (LLMContextFrame, LLMMessagesAppendFrame, LLMRunFrame)
_SHUTDOWN_FRAMES = (EndFrame, CancelFrame, StopFrame)


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


def _utterance_from_turn(frame: Frame, context: LLMContext) -> str:
    if isinstance(frame, LLMMessagesAppendFrame):
        text = _last_user_text(list(frame.messages or []))
        if text:
            return text
    return _last_user_text(context.get_messages())


def drop_last_user_message(context: LLMContext) -> bool:
    """Remove a crisis turn so it cannot steer the math tutor."""
    messages = context.messages
    if not messages:
        return False
    last = messages[-1]
    if last.get("role") != "user":
        return False
    messages.pop()
    return True


class SafetyProcessor(FrameProcessor):
    """Intercept high-risk turns; speak a canned safety reply; pause tutoring."""

    def __init__(
        self,
        store: SafetyStore,
        llm_context: LLMContext,
        session_store: SessionContextStore,
        *,
        session_id: str = "-",
        get_language: Callable[[], str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._store = store
        self._llm_context = llm_context
        self._session_store = session_store
        self._session_id = session_id
        self._get_language = get_language
        self._last_handled: str = ""
        logger.info("[Safety] processor ready | session={}", self._session_id)

    def _language(self) -> str:
        if self._get_language is None:
            return LANG_EN
        return self._get_language() or LANG_EN

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, _SHUTDOWN_FRAMES):
            self._store.reset()
            self._last_handled = ""
            await self.push_frame(frame, direction)
            return

        if direction != FrameDirection.DOWNSTREAM or not isinstance(
            frame, _LLM_TURN_FRAMES
        ):
            await self.push_frame(frame, direction)
            return

        utterance = _utterance_from_turn(frame, self._llm_context)
        if not utterance:
            await self.push_frame(frame, direction)
            return

        if utterance == self._last_handled and self._store.paused:
            return

        result = self._store.apply(
            utterance,
            language=self._language(),
            now=time.time(),
        )
        if result is None:
            self._last_handled = ""
            await self.push_frame(frame, direction)
            return
        self._last_handled = utterance

        logger.warning(
            "[Safety] session={} kind={} swallow={} category={} utterance_len={}",
            self._session_id,
            result.kind.value,
            result.swallow,
            (result.event or {}).get("category"),
            len(utterance),
        )
        await self._deliver(result)
        if not result.swallow:
            await self.push_frame(frame, direction)

    async def _deliver(self, result: SafetyTurnResult) -> None:
        if result.drop_last_user:
            drop_last_user_message(self._llm_context)
            upsert_context_system_note(
                self._llm_context,
                SAFETY_CONTEXT_MARKER,
                SAFETY_CONTEXT_NOTE,
            )
        if result.event and result.event.get("type"):
            await self.push_frame(
                OutputTransportMessageFrame(message=result.event),
                FrameDirection.DOWNSTREAM,
            )
        if result.spoken:
            if result.force_speak:
                self._session_store.skip_tts_next_response = False
            # One TTS request for the whole script. A bare TextFrame is split
            # on periods into concurrent Cartesia contexts (limit 2), so the
            # caring reply was cutting off after the first sentence.
            await self.push_frame(
                TTSSpeakFrame(text=result.spoken, append_to_context=False),
                FrameDirection.DOWNSTREAM,
            )
