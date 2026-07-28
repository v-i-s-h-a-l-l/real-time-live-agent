"""Drop duplicate STT transcriptions that would otherwise trigger two LLM turns."""

from __future__ import annotations

import re
import time

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame, UserStartedSpeakingFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class TranscriptionDedupProcessor(FrameProcessor):
    """Suppress identical TranscriptionFrames within a short time window."""

    def __init__(self, *, window_secs: float = 4.0, **kwargs):
        super().__init__(**kwargs)
        self._window = window_secs
        self._last_text = ""
        self._last_at = 0.0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, UserStartedSpeakingFrame):
            self._last_text = ""
            self._last_at = 0.0
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            raw = (frame.text or "").strip()
            text = re.sub(r"\s+", " ", raw.lower())
            if text:
                now = time.monotonic()
                if text == self._last_text and (now - self._last_at) < self._window:
                    logger.debug("[TranscriptionDedup] dropped duplicate: {!r}", text[:80])
                    return
                self._last_text = text
                self._last_at = now

        await self.push_frame(frame, direction)
