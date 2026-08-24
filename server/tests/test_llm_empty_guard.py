"""Empty-guard must not close a late Groq turn."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipecat.frames.frames import (  # noqa: E402
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TextFrame,
)
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402

from processors.llm_empty_guard import LLMEmptyGuardProcessor  # noqa: E402
from services.llm_retry import LLMRetryInProgressFrame  # noqa: E402


def test_timeout_hold_does_not_end_the_llm_turn():
    async def run() -> None:
        guard = LLMEmptyGuardProcessor(timeout_secs=0.05)
        pushed: list = []

        async def capture(frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

        guard.push_frame = capture
        await guard.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await asyncio.sleep(0.12)
        hold = [f for f in pushed if isinstance(f, TextFrame)]
        assert hold
        assert not any(isinstance(f, LLMFullResponseEndFrame) for f in pushed)

        await guard.process_frame(TextFrame(text="Here is the real reply."), FrameDirection.DOWNSTREAM)
        texts = [f.text for f in pushed if isinstance(f, TextFrame)]
        assert "Here is the real reply." in texts

    asyncio.run(run())


def test_retry_frame_delays_timeout_filler():
    """Empty-guard must not fire while LLM retries are still in flight."""

    async def run() -> None:
        guard = LLMEmptyGuardProcessor(timeout_secs=0.08)
        pushed: list = []

        async def capture(frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

        guard.push_frame = capture
        await guard.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await asyncio.sleep(0.05)
        await guard.process_frame(
            LLMRetryInProgressFrame(attempt=1, status=429),
            FrameDirection.DOWNSTREAM,
        )
        await asyncio.sleep(0.05)
        assert not any(isinstance(f, TextFrame) for f in pushed)

        await asyncio.sleep(0.08)
        hold = [f for f in pushed if isinstance(f, TextFrame)]
        assert hold

    asyncio.run(run())


def test_empty_end_still_injects_after_retries_exhausted():
    async def run() -> None:
        guard = LLMEmptyGuardProcessor(timeout_secs=5.0)
        pushed: list = []

        async def capture(frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

        guard.push_frame = capture
        await guard.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await guard.process_frame(
            LLMRetryInProgressFrame(attempt=2, status=503),
            FrameDirection.DOWNSTREAM,
        )
        await guard.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
        texts = [f.text for f in pushed if isinstance(f, TextFrame)]
        assert texts, "last-resort filler must still fire after retries exhaust"

    asyncio.run(run())

