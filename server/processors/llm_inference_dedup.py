"""Drop duplicate LLMContextFrame triggers for the same user utterance."""

from __future__ import annotations

import re
import time

from loguru import logger
from pipecat.frames.frames import Frame, LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from processors.llm_context_text import _last_user_text


def _normalize_user_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


class LLMInferenceDedupProcessor(FrameProcessor):
    """Suppress back-to-back LLM runs for identical user text."""

    def __init__(self, *, window_secs: float = 6.0, **kwargs):
        super().__init__(**kwargs)
        self._window = window_secs
        self._last_text = ""
        self._last_at = 0.0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMContextFrame):
            messages = frame.context.get_messages() if frame.context else []
            text = _normalize_user_text(_last_user_text(messages))
            if text:
                now = time.monotonic()
                if text == self._last_text and (now - self._last_at) < self._window:
                    logger.info(
                        "[LLMInferenceDedup] dropped duplicate inference for: {!r}",
                        text[:80],
                    )
                    return
                self._last_text = text
                self._last_at = now

        await self.push_frame(frame, direction)
