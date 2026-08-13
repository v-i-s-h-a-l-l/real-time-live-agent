"""LanguageTrackerProcessor: active-language state, hysteresis, explicit switch.

Exercises the tracker's decision logic (``_maybe_switch``) directly so we do not
need a running Pipecat task. Captures the frames it would push so we can assert
the TTS-language update and that no system message is injected into the context.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipecat.frames.frames import TranscriptionFrame, TTSUpdateSettingsFrame  # noqa: E402
from pipecat.transcriptions.language import Language  # noqa: E402

from languages import LANG_EN, LANG_HI, LANG_TA, LANG_TE  # noqa: E402
from processors.language_tracker import LanguageTrackerProcessor  # noqa: E402


class _FakeContext:
    def __init__(self):
        self.messages: list[dict] = []

    def add_message(self, message):  # pragma: no cover - must never be called
        self.messages.append(message)


def _make_tracker(initial=LANG_EN, confirmations=2):
    ctx = _FakeContext()
    tracker = LanguageTrackerProcessor(
        context=ctx,
        session_id="test",
        initial_language=initial,
        min_chars=8,
        min_confidence=0.55,
        confirmations_needed=confirmations,
    )
    pushed: list = []

    async def _capture(frame, direction=None):
        pushed.append(frame)

    tracker.push_frame = _capture  # type: ignore[assignment]
    return tracker, ctx, pushed


def _feed(tracker, text, sarvam=None):
    frame = TranscriptionFrame(text=text, user_id="u", timestamp="t", language=sarvam)
    asyncio.run(tracker._maybe_switch(frame))


def _tts_langs(pushed):
    return [
        getattr(f.delta, "language", None)
        for f in pushed
        if isinstance(f, TTSUpdateSettingsFrame)
    ]


def test_tracker_never_appends_system_message():
    tracker, ctx, _ = _make_tracker()
    _feed(tracker, "मुझे ये concept समझ नहीं आया अभी", sarvam=Language.HI_IN)
    assert ctx.messages == []  # language lives in the per-turn directive, not context


def test_full_hindi_sentence_switches_and_updates_tts():
    tracker, _, pushed = _make_tracker(initial=LANG_EN)
    _feed(tracker, "इस slide को मुझे समझाओ please", sarvam=Language.HI_IN)
    assert tracker.current_language == LANG_HI
    assert Language.HI in _tts_langs(pushed)


def test_hindi_stays_hindi_on_continued_hindi_turn():
    tracker, _, pushed = _make_tracker(initial=LANG_HI)
    _feed(tracker, "यह थोड़ा boring है यार", sarvam=Language.HI_IN)
    assert tracker.current_language == LANG_HI
    # No churn: same language means no TTS-language frame.
    assert _tts_langs(pushed) == []


def test_short_english_ack_does_not_switch_from_hindi():
    tracker, _, _ = _make_tracker(initial=LANG_HI)
    for ack in ("Okay.", "yes", "haan", "right", "achha"):
        _feed(tracker, ack, sarvam=Language.EN_IN)
    assert tracker.current_language == LANG_HI


def test_one_english_clause_does_not_flip_established_hindi_immediately():
    # A single confident English clause is held by hysteresis (needs 2).
    tracker, _, _ = _make_tracker(initial=LANG_HI, confirmations=2)
    _feed(tracker, "can you explain this equation", sarvam=Language.EN_IN)
    assert tracker.current_language == LANG_HI
    # Sustained English → switch.
    _feed(tracker, "I really did not understand that part", sarvam=Language.EN_IN)
    assert tracker.current_language == LANG_EN


def test_code_mixed_hindi_keeps_hindi():
    tracker, _, _ = _make_tracker(initial=LANG_HI)
    _feed(tracker, "इस equation को substitution method से solve करेंगे", sarvam=Language.EN_IN)
    assert tracker.current_language == LANG_HI


def test_explicit_switch_to_english_overrides_hindi_speech():
    tracker, _, pushed = _make_tracker(initial=LANG_HI)
    _feed(tracker, "अब English में समझाओ", sarvam=Language.HI_IN)
    assert tracker.current_language == LANG_EN
    assert Language.EN in _tts_langs(pushed)


def test_explicit_switch_back_to_hindi():
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    _feed(tracker, "talk to me in Hindi", sarvam=Language.EN_IN)
    assert tracker.current_language == LANG_HI


def test_telugu_sentence_switches_to_telugu():
    tracker, _, pushed = _make_tracker(initial=LANG_EN)
    _feed(tracker, "ఈ slide ఏమి చెబుతుంది సార్", sarvam=Language.TE_IN)
    assert tracker.current_language == LANG_TE
    assert Language.TE in _tts_langs(pushed)


def test_tamil_sentence_switches_to_tamil():
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    _feed(tracker, "இந்த equation-ஐ step by step பாப்போம் சார்", sarvam=Language.TA_IN)
    assert tracker.current_language == LANG_TA
