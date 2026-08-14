"""Incidental barge-in (cough) auto-resumes; meaningful speech stays a real interrupt."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.incidental_resume import (  # noqa: E402
    IncidentalResumeCaptureProcessor,
    IncidentalResumeGateProcessor,
    IncidentalResumeStore,
    is_incidental_utterance,
    remainder_after_cut,
    restore_assistant_text,
)
from pipecat.frames.frames import (  # noqa: E402
    InterruptionFrame,
    LLMFullResponseStartFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402


def test_cough_and_fillers_are_incidental():
    for text in (
        "",
        "   ",
        "...",
        "uh",
        "um",
        "hmm",
        "ahem",
        "cough",
        "*cough*",
        "[cough]",
        "(sneeze)",
        "uh um",
    ):
        assert is_incidental_utterance(text), text


def test_short_meaningful_utterances_are_not_incidental():
    for text in (
        "Why?",
        "How?",
        "Wait.",
        "No.",
        "What?",
        "Wait, why do we multiply the equation?",
        "yes",
        "okay",
        "x",
        "y",
        "5",
        "continue",
        "go on",
    ):
        assert not is_incidental_utterance(text), text


def test_english_words_are_not_incidental():
    assert not is_incidental_utterance("Why is this equation important?")
    assert not is_incidental_utterance("Yes, exactly.")


def test_tamil_and_hindi_speech_is_not_incidental():
    assert not is_incidental_utterance("ஒரு எக்ஸாம்பிளோட எக்ஸ்பிளைன் பண்றியா?")
    assert not is_incidental_utterance("எக்ஸாம்பிள் கொடுக்கிறியா?")
    assert not is_incidental_utterance(
        "இல்லை, இப்படி வெறுமனே எக்ஸ்பிளைன் பண்ணாத, ஒரு எக்ஸாம்பிளோடு எக்ஸ்பிளைன் பண்ணு எனக்கு."
    )
    assert not is_incidental_utterance("उदाहरण के साथ समझाइए")
    assert not is_incidental_utterance("एक example दो")


def test_remainder_does_not_restart_the_explanation():
    text = (
        "First, we multiply the first equation by two. "
        "Then we add the two equations together to eliminate y."
    )
    remainder = remainder_after_cut(text, 65)
    assert remainder
    assert not remainder.startswith("First, we multiply")
    assert "eliminate" in remainder


def test_store_keeps_unspoken_tail_after_interrupt():
    store = IncidentalResumeStore()
    store.begin_turn()
    store.append_spoken(
        "Sure! In the elimination method you scale each equation so a variable matches. "
        "Then you add or subtract the equations to eliminate y."
    )
    store.on_bot_started()
    store.on_interrupted()
    assert store.pending
    assert "eliminate" in store.remainder
    assert store.remainder != store.full_text or len(store.remainder) > 12


def test_meaningful_abort_does_not_resume():
    store = IncidentalResumeStore()
    store.begin_turn()
    store.append_spoken("First we multiply the first equation by two and then we add them.")
    store.on_interrupted()
    assert store.pending
    assert not store.should_resume("Wait, why do we multiply the equation?", user_secs=1.0)
    store.abort()
    assert not store.pending
    assert store.consume_resume() is None


def test_incidental_should_resume():
    store = IncidentalResumeStore()
    store.begin_turn()
    store.append_spoken("First we multiply the first equation by two and then we add them.")
    store.on_interrupted()
    assert store.should_resume("cough", user_secs=0.4)
    assert store.should_resume("", user_secs=0.4)
    assert store.should_resume("uh", user_secs=0.3)


def test_long_empty_turn_is_not_treated_as_cough():
    store = IncidentalResumeStore()
    store.begin_turn()
    store.append_spoken("First we multiply the first equation by two and then we add them.")
    store.on_interrupted()
    assert not store.should_resume("", user_secs=2.0)


def test_restore_replaces_truncated_assistant():
    class Ctx:
        def __init__(self):
            self.messages = [{"role": "assistant", "content": "First we"}]

        def add_message(self, msg):
            self.messages.append(msg)

    ctx = Ctx()
    restore_assistant_text(ctx, "First we multiply, then we add.")
    assert ctx.messages[-1]["content"] == "First we multiply, then we add."
    assert len(ctx.messages) == 1


class _FakeContext:
    def __init__(self):
        self.messages = []

    def add_message(self, msg):
        self.messages.append(msg)


def _transcription(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u", timestamp="t")


def test_gate_resumes_on_cough_without_waiting_for_user_stop():
    async def run() -> None:
        store = IncidentalResumeStore()
        store.begin_turn()
        store.append_spoken(
            "First, we multiply the first equation by two. "
            "Then we add the two equations together to eliminate y."
        )
        store.on_interrupted()
        ctx = _FakeContext()
        gate = IncidentalResumeGateProcessor(store=store, context=ctx)
        pushed: list = []

        async def capture(frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

        gate.push_frame = capture

        await gate.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
        await gate.process_frame(_transcription("cough"), FrameDirection.DOWNSTREAM)
        assert not any(isinstance(f, TranscriptionFrame) for f in pushed)

        speak = [f for f in pushed if isinstance(f, TTSSpeakFrame)]
        assert len(speak) == 1
        assert "eliminate" in speak[0].text
        assert speak[0].append_to_context is False

    asyncio.run(run())


def test_gate_passes_meaningful_interruption():
    async def run() -> None:
        store = IncidentalResumeStore()
        store.begin_turn()
        store.append_spoken(
            "First, we multiply the first equation by two. "
            "Then we add the two equations together to eliminate y."
        )
        store.on_interrupted()
        gate = IncidentalResumeGateProcessor(store=store, context=_FakeContext())
        pushed: list = []

        async def capture(frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

        gate.push_frame = capture

        await gate.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
        await gate.process_frame(
            _transcription("Wait, why do we multiply the equation?"),
            FrameDirection.DOWNSTREAM,
        )
        assert any(isinstance(f, TranscriptionFrame) for f in pushed)
        assert not any(isinstance(f, TTSSpeakFrame) for f in pushed)
        assert not store.pending

    asyncio.run(run())


def test_capture_records_spoken_text():
    async def run() -> None:
        store = IncidentalResumeStore()
        cap = IncidentalResumeCaptureProcessor(store=store)

        async def noop(*_a, **_k):
            return None

        cap.push_frame = noop

        await cap.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await cap.process_frame(
            TextFrame(text="First we multiply the first equation by two. "),
            FrameDirection.DOWNSTREAM,
        )
        store.on_interrupted()
        assert store.pending
        assert "multiply" in store.full_text

    asyncio.run(run())
