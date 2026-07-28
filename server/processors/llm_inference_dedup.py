"""Drop duplicate LLMContextFrame triggers for the same user utterance."""

from __future__ import annotations

import re
import time

from loguru import logger
from pipecat.frames.frames import Frame, LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


def _normalize_user_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


class LLMInferenceDedupProcessor(FrameProcessor):
    """Suppress back-to-back LLM runs for identical user text."""

    def __init__(self, *, window_secs: float = 6.0, **kwargs):
        super().__init__(**kwargs)
        self._window = window_secs
        self._last_text = ""
        self._last_at = 0.0

    def _last_user_text(self, frame: LLMContextFrame) -> str:
        messages = frame.context.get_messages() if frame.context else []
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
                text = content or ""
            text = str(text).strip()
            if text:
                return text
        return ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMContextFrame):
            text = _normalize_user_text(self._last_user_text(frame))
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
