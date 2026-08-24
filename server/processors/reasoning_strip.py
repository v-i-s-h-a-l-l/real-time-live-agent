"""Strip Qwen/Groq reasoning blocks from streamed LLM text before TTS."""

from __future__ import annotations

import re

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    TextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

_THINKING_BLOCK = re.compile(
    r"<think>.*?</think>",
    re.DOTALL | re.IGNORECASE,
)
_THINKING_OPEN = re.compile(r"<think>", re.IGNORECASE)


def strip_thinking_block(text: str) -> str:
    """Remove <think>...</think> blocks, keep the reply."""
    cleaned = _THINKING_BLOCK.sub("", text)
    return cleaned.strip()


class ReasoningStripProcessor(FrameProcessor):
    """Drop reasoning tags from streaming LLM chunks before naturalizer/TTS."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._carry = ""

    def _strip_chunk(self, chunk: str) -> str:
        if not chunk and not self._carry:
            return ""

        text = self._carry + chunk
        self._carry = ""
        text = _THINKING_BLOCK.sub("", text)

        open_match = _THINKING_OPEN.search(text)
        if open_match is not None:
            tail = text[open_match.start() :]
            if "</think>" not in tail.lower():
                self._carry = tail
                text = text[: open_match.start()]

        return text

    def _reset(self):
        self._carry = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            cleaned = self._strip_chunk(frame.text)
            if cleaned:
                await self.push_frame(TextFrame(text=cleaned), direction)
            return

        if isinstance(frame, (LLMFullResponseEndFrame, InterruptionFrame)):
            self._reset()

        await self.push_frame(frame, direction)
