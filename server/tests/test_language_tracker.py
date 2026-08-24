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

from languages import (  # noqa: E402
    LANG_EN,
    LANG_HI,
    LANG_TA,
    LANG_TE,
    SCRIPT_NATIVE,
    SCRIPT_ROMAN,
)
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
    assert tracker.current_script == SCRIPT_NATIVE


def test_typed_explicit_tamil_stays_through_roman_followups():
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    asyncio.run(tracker.observe_utterance("speak in Tamil please"))
    assert tracker.current_language == LANG_TA
    assert tracker.current_script == SCRIPT_ROMAN
    for text in ("ok next slide", "yes ready", "enna solve pannu"):
        asyncio.run(tracker.observe_utterance(text))
    assert tracker.current_language == LANG_TA
    assert tracker.current_script == SCRIPT_ROMAN


def test_tanglish_after_tamil_does_not_count_as_english():
    tracker, _, _ = _make_tracker(initial=LANG_TA)
    _feed(tracker, "enna panrom next", sarvam=Language.EN_IN)
    _feed(tracker, "seri next slide", sarvam=Language.EN_IN)
    assert tracker.current_language == LANG_TA


def test_native_tamil_script_is_not_flipped_by_short_latin_ack():
    tracker, _, _ = _make_tracker(initial=LANG_TA)
    _feed(tracker, "இந்த equation-ஐ step by step பாப்போம் சார்", sarvam=Language.TA_IN)
    assert tracker.current_script == SCRIPT_NATIVE
    _feed(tracker, "ok", sarvam=Language.EN_IN)
    assert tracker.current_language == LANG_TA
    assert tracker.current_script == SCRIPT_NATIVE


def test_explicit_english_still_leaves_an_indic_session():
    tracker, _, _ = _make_tracker(initial=LANG_TA)
    asyncio.run(tracker.observe_utterance("talk in English please"))
    assert tracker.current_language == LANG_EN


def test_capability_question_switches_to_that_language():
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    asyncio.run(tracker.observe_utterance("hindi malum hai kya"))
    assert tracker.current_language == LANG_HI
    assert tracker.current_script == SCRIPT_ROMAN

    tracker2, _, _ = _make_tracker(initial=LANG_EN)
    asyncio.run(tracker2.observe_utterance("tamil theriyuma"))
    assert tracker2.current_language == LANG_TA
    assert tracker2.current_script == SCRIPT_ROMAN


def test_substantive_roman_hinglish_overrides_english_stickiness():
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    asyncio.run(tracker.observe_utterance("yaar mujhe ye samajh nahi aa raha"))
    assert tracker.current_language == LANG_HI
    assert tracker.current_script == SCRIPT_ROMAN


def test_substantive_roman_tanglish_overrides_english_stickiness():
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    asyncio.run(tracker.observe_utterance("enna pannu neenga sollunga"))
    assert tracker.current_language == LANG_TA


def test_substantive_roman_tenglish_overrides_english_stickiness():
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    asyncio.run(tracker.observe_utterance("nenu enti cheppu meeru"))
    assert tracker.current_language == LANG_TE


def test_clear_hindi_switch_overrides_tamil_stickiness():
    tracker, _, _ = _make_tracker(initial=LANG_TA)
    asyncio.run(tracker.observe_utterance("mujhe hindi mein samajhna hai yaar"))
    assert tracker.current_language == LANG_HI


def test_clear_tamil_switch_after_hindi_turn_regression():
    """User reported: Hindi turn, then 'ennada ivlo kastama iruku' → must be Tamil."""
    tracker, _, _ = _make_tracker(initial=LANG_EN)
    asyncio.run(tracker.observe_utterance("yeh concept bahut mushkil hai"))
    assert tracker.current_language == LANG_HI
    asyncio.run(tracker.observe_utterance("ennada ivlo kastama iruku"))
    assert tracker.current_language == LANG_TA
    assert tracker.current_script == SCRIPT_ROMAN
