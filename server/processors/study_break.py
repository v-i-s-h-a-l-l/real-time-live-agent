"""Study-break turn interceptor.

Sits after typed `text_input` and the user aggregator, before Tutor Engine /
LLM. Voice and typed turns both arrive as LLMContextFrame, so one processor
covers both. Audio, VAD, STT, TTS, and interruption are untouched.

The timer is an event-loop deadline (`call_later` to the absolute end
timestamp), not a sleep on the frame-processing path. BREAK_END is delivered
once through the existing TextFrame → TTS pipeline plus a WebSocket event.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    LLMContextFrame,
    LLMRunFrame,
    OutputTransportMessageFrame,
    StopFrame,
    TextFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from processors.session_context import SessionContextStore
from security import redact_utterance
from tutor.breaks import BreakPhase, BreakStore, BreakTurnResult

_LLM_TURN_FRAMES = (LLMContextFrame, LLMRunFrame)
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


def drop_last_user_message(context: LLMContext) -> bool:
    """Remove a during-break chatter turn so it cannot steer the next lesson."""
    messages = context.messages
    if not messages:
        return False
    last = messages[-1]
    if last.get("role") != "user":
        return False
    messages.pop()
    return True


class StudyBreakProcessor(FrameProcessor):
    """Intercept break/resume turns; schedule one completion callback."""

    def __init__(
        self,
        store: BreakStore,
        llm_context: LLMContext,
        session_store: SessionContextStore,
        *,
        session_id: str = "-",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._store = store
        self._llm_context = llm_context
        self._session_store = session_store
        self._session_id = session_id
        self._timer_handle: asyncio.TimerHandle | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_handled: str = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, _SHUTDOWN_FRAMES):
            self._cancel_timer()
            self._store.reset()
            await self.push_frame(frame, direction)
            return

        if direction != FrameDirection.DOWNSTREAM or not isinstance(frame, _LLM_TURN_FRAMES):
            await self.push_frame(frame, direction)
            return

        utterance = _last_user_text(self._llm_context.get_messages())
        if not utterance:
            await self.push_frame(frame, direction)
            return

        # A second LLMContextFrame for the same already-handled turn must not
        # start another timer or re-speak the acknowledgement.
        if (
            utterance == self._last_handled
            and self._store.state.phase != BreakPhase.IDLE
        ):
            return

        result = self._store.apply(utterance, time.time())
        if result is None:
            self._last_handled = ""
            await self.push_frame(frame, direction)
            return
        self._last_handled = utterance

        logger.info(
            "[StudyBreak] session={} phase={} swallow={} event={} utterance={}",
            self._session_id,
            self._store.state.phase.value,
            result.swallow,
            result.event.get("type") if result.event else None,
            redact_utterance(utterance),
        )
        await self._deliver(result, force_speak=False)
        if not result.swallow:
            await self.push_frame(frame, direction)

    async def _deliver(self, result: BreakTurnResult, *, force_speak: bool) -> None:
        if result.drop_last_user:
            drop_last_user_message(self._llm_context)
        if result.cancel_timer:
            self._cancel_timer()
        if result.schedule:
            self._arm_timer()
        if result.event and result.event.get("type"):
            await self.push_frame(
                OutputTransportMessageFrame(message=result.event),
                FrameDirection.DOWNSTREAM,
            )
        if result.spoken:
            if force_speak:
                self._session_store.skip_tts_next_response = False
            text = TextFrame(text=result.spoken)
            await self.push_frame(text, FrameDirection.DOWNSTREAM)

    def _arm_timer(self) -> None:
        self._cancel_timer()
        ends_at = self._store.state.ends_at
        if ends_at is None:
            return
        delay = max(0.0, ends_at - time.time())
        generation = self._store.generation
        loop = asyncio.get_running_loop()
        self._loop = loop
        # Absolute deadline: remaining is computed from endsAt, not a tick count.
        self._timer_handle = loop.call_later(delay, self._on_deadline, generation)
        logger.info(
            "[StudyBreak] timer armed session={} generation={} delay={:.1f}s ends_at={}",
            self._session_id,
            generation,
            delay,
            ends_at,
        )

    def _on_deadline(self, generation: int) -> None:
        # call_later callback must not await; hop back onto the processor loop.
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.create_task(self._fire_end(generation))

    async def _fire_end(self, generation: int) -> None:
        ends_at = self._store.state.ends_at
        if (
            generation == self._store.generation
            and ends_at is not None
            and time.time() < ends_at - 0.05
        ):
            self._arm_timer()
            return
        result = self._store.expire(time.time(), generation)
        if result is None:
            logger.info(
                "[StudyBreak] BREAK_END ignored session={} generation={}",
                self._session_id,
                generation,
            )
            return
        logger.info(
            "[StudyBreak] BREAK_END session={} duration={}",
            self._session_id,
            result.event.get("durationMinutes"),
        )
        await self._deliver(result, force_speak=True)

    def _cancel_timer(self) -> None:
        handle = self._timer_handle
        self._timer_handle = None
        if handle is not None and not handle.cancelled():
            handle.cancel()
