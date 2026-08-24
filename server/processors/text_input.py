"""Inject typed student messages into the existing tutor turn path.

Does not create a parallel LLM/chat backend. Typed text becomes a user
message on the same LLMContext, then the existing Tutor Engine + LLM + TTS
path runs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputTransportMessageFrame,
    InterruptionFrame,
    LLMContextFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from processors.session_context import SessionContextStore
from protocol import CLIENT_TEXT_INPUT, is_client_message
from security import clip_text_input


def parse_text_input(message: Any) -> tuple[str, str, bool] | None:
    """Return (text, message_id, speak) if this is a text_input control message."""
    if not is_client_message(message, CLIENT_TEXT_INPUT):
        return None
    text = str(message.get("text") or message.get("message") or "").strip()
    if not text:
        return None
    text = clip_text_input(text)
    message_id = str(message.get("messageId") or message.get("id") or "")
    speak_raw = message.get("speak", True)
    speak = True if speak_raw is None else bool(speak_raw)
    return text, message_id, speak


class TextInputProcessor(FrameProcessor):
    """Handle `{type: text_input}` on the voice WebSocket.

    Placed after the user aggregator so typed text does not enter VAD/STT
    aggregation, then:
      1. optional barge-in interrupt
      2. append user message to the shared LLMContext
      3. emit LLMContextFrame so TutorTurnProcessor + LLM run as for voice
    """

    def __init__(
        self,
        store: SessionContextStore,
        llm_context: LLMContext,
        *,
        session_id: str = "-",
        observe_language: Callable[..., Awaitable[None]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._store = store
        self._llm_context = llm_context
        self._session_id = session_id
        self._observe_language = observe_language

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InterruptionFrame):
            self._store.skip_tts_next_response = False

        if isinstance(frame, InputTransportMessageFrame):
            parsed = parse_text_input(frame.message)
            if parsed is not None:
                text, message_id, speak = parsed
                logger.info(
                    "[TextInput] session={} messageId={} chars={} speak={} section={} question={}",
                    self._session_id,
                    message_id or "-",
                    len(text),
                    speak,
                    (self._store.learning_context or {}).get("sectionId"),
                    (self._store.learning_context or {}).get("questionId"),
                )
                self._store.skip_tts_next_response = not speak
                await self.broadcast_interruption()
                self._llm_context.add_message({"role": "user", "content": text})
                if self._observe_language is not None:
                    await self._observe_language(text)
                await self.push_frame(
                    LLMContextFrame(context=self._llm_context),
                    direction,
                )
                return

        await self.push_frame(frame, direction)
