"""Tests for CallMute unmute / re-engagement phrases."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipecat.frames.frames import TranscriptionFrame, UserStoppedSpeakingFrame  # noqa: E402
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402

from processors.call_mute import (  # noqa: E402
    CallMuteProcessor,
    _MUTE_RE,
    _UNMUTE_RE,
    _looks_like_lesson_utterance,
    _matches,
)


def test_unmute_i_am_back():
    assert _matches("hey I am back after call", _UNMUTE_RE)
    assert _matches("hey I'm back", _UNMUTE_RE)
    assert _matches("I am back", _UNMUTE_RE)
    assert _matches("I'm back now", _UNMUTE_RE)
    assert _matches("Im back", _UNMUTE_RE)


def test_unmute_after_call_phrases():
    assert _matches("back after the call", _UNMUTE_RE)
    assert _matches("hey I am back after call to the voice assistant", _UNMUTE_RE)
    assert _matches("done with the call", _UNMUTE_RE)
    assert _matches("the call is over", _UNMUTE_RE)
    assert _matches("I am back now", _UNMUTE_RE)


def test_unmute_presence_checks():
    assert _matches("are you there", _UNMUTE_RE)
    assert _matches("can you hear me", _UNMUTE_RE)
    assert _matches("hello", _UNMUTE_RE)


def test_ministros_is_not_an_unmute_phrase():
    assert not _matches("ministros", _UNMUTE_RE)
    assert not _matches("ministro", _UNMUTE_RE)


def test_mute_still_triggers_on_step_away():
    assert _matches("I am taking a call", _MUTE_RE)
    assert _matches("one second", _MUTE_RE)
    assert _matches("hold on", _MUTE_RE)


def test_study_break_skip_prevents_one_minute_mute():
    processor = CallMuteProcessor(should_skip_mute=lambda text: "minute" in text.lower())
    assert processor._should_skip_mute is not None
    assert processor._should_skip_mute("one minute")
    assert not processor._muted


def _tx(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u", timestamp="t")


def _processor(*, clock: list[float], timeout_secs: float = 40.0) -> CallMuteProcessor:
    return CallMuteProcessor(now=lambda: clock[0], timeout_secs=timeout_secs)


def _run(processor: CallMuteProcessor, frame) -> list:
    pushed: list = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        pushed.append(frame)

    async def run() -> None:
        processor.push_frame = capture  # type: ignore[method-assign]
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    asyncio.run(run())
    return pushed


def test_auto_unmute_after_timeout_without_unmute_phrase():
    clock = [1_000.0]
    processor = _processor(clock=clock, timeout_secs=40)
    _run(processor, _tx("hold on"))
    assert processor._muted

    _run(processor, _tx("um"))
    assert processor._muted

    clock[0] += 41
    _run(processor, UserStoppedSpeakingFrame())
    assert not processor._muted


def test_substantial_lesson_utterance_unmutes_before_timeout():
    clock = [1_000.0]
    processor = _processor(clock=clock, timeout_secs=40)
    _run(processor, _tx("one second"))
    assert processor._muted

    pushed = _run(
        processor,
        _tx("can you explain the quadratic formula one more time"),
    )
    assert not processor._muted
    assert any(
        isinstance(frame, TranscriptionFrame)
        and "quadratic formula" in (frame.text or "")
        for frame in pushed
    )


def test_short_filler_does_not_unmute_before_timeout():
    clock = [1_000.0]
    processor = _processor(clock=clock, timeout_secs=40)
    _run(processor, _tx("hold on"))
    pushed = _run(processor, _tx("yeah wait"))
    assert processor._muted
    assert pushed == []


def test_lesson_utterance_helper_rejects_fillers_and_hold_on():
    assert not _looks_like_lesson_utterance("yeah um wait ok like so", min_words=6)
    assert not _looks_like_lesson_utterance("hold on", min_words=6)
    assert _looks_like_lesson_utterance(
        "please show me the next step of this problem",
        min_words=6,
    )
