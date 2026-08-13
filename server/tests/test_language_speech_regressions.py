"""P0 regression guards: maths pronunciation, punctuation, and directive placement.

Covers the four regressions that appeared once the tutor reliably stayed in an
Indic language: mathematical variables read with Indic phonetics, full stops
spoken as "dot", LaTeX environment names spelled out, and the per-turn language
directive being outranked by the English conversation history.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipecat.frames.frames import TextFrame  # noqa: E402
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402

from processors.naturalizer import ResponseNaturalizerProcessor  # noqa: E402
from processors.session_context import upsert_context_system_note  # noqa: E402
from processors.speak_math import speak_for_tts  # noqa: E402
from tutor.prompts import response_language_directive  # noqa: E402


# ── 13. mathematical variables must not depend on the TTS voice's language ──

def test_indic_voice_gets_english_letter_names():
    for lang in ("hi", "ta", "te"):
        spoken = speak_for_tts("$x + y = 5$", speech_language=lang)
        assert "why" in spoken, lang
        assert "ex" in spoken, lang


def test_english_voice_also_uses_letter_names():
    """Bare 'y' is 'ee' on Indic voices; letter names keep every voice consistent."""
    spoken = speak_for_tts("$x + y = 5$", speech_language="en")
    assert "ex plus why equals five" in spoken


def test_default_matches_named_english():
    assert speak_for_tts("$x + y = 5$") == speak_for_tts("$x + y = 5$", speech_language="en")


# ── 14. ordinary English must survive in every language ──

def test_prose_is_never_spelled_out_in_any_language():
    text = "The remainder is smaller than the divisor, and the quotient is a coefficient."
    for lang in ("en", "hi", "ta", "te"):
        spoken = speak_for_tts(text, speech_language=lang)
        assert "remainder" in spoken, lang
        assert "divisor" in spoken, lang
        assert "quotient" in spoken, lang
        assert "coefficient" in spoken, lang
        assert "are ee em" not in spoken, lang


def test_indic_sentence_keeps_its_words_and_fixes_only_the_maths():
    spoken = speak_for_tts("इस formula में $y$ की value क्या है?", speech_language="hi")
    assert "formula" in spoken
    assert "value" in spoken
    assert "why" in spoken


# ── 16. existing maths behaviour is unchanged ──

def test_required_math_readings_hold_in_both_modes():
    for lang in ("en", "hi"):
        assert speak_for_tts("$x^2$", speech_language=lang) == "ex squared."
        assert speak_for_tts("$x^3$", speech_language=lang) == "ex cubed."
        assert speak_for_tts("$-b/a$", speech_language=lang) == (
            "negative bee divided by ay."
        )
        assert "the square root of" in speak_for_tts(r"$\sqrt{x}$", speech_language=lang)


# ── 15. notation must never reach the voice as literal symbols ──

def test_latex_environment_name_is_not_spelled_out():
    block = r"\[ \begin{cases} 2x + 3y = 12 \\ x - y = 1 \end{cases} \]"
    for lang in ("en", "hi", "ta"):
        spoken = speak_for_tts(block, speech_language=lang)
        assert "cases" not in spoken, lang
        assert "see ay ess" not in spoken, lang
        assert "\\" not in spoken, lang
        # The two stacked equations stay separate instead of running together.
        assert spoken.count("equals") == 2, lang


def test_aligned_environment_and_alignment_markers_are_dropped():
    spoken = speak_for_tts(
        r"\[ \begin{aligned} x &= 2y + 3 \\ y &= 4 \end{aligned} \]",
        speech_language="en",
    )
    assert "aligned" not in spoken
    assert "&" not in spoken
    assert "ex equals two why plus three" in spoken


def test_flushed_sentences_do_not_weld_into_a_dot():
    """"three.அப்பா" is read as a domain name, so TTS says the full stop aloud."""
    processor = ResponseNaturalizerProcessor(add_starters=False)
    pushed: list[str] = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        if isinstance(frame, TextFrame):
            pushed.append(frame.text)

    processor.push_frame = capture

    async def run() -> None:
        processor._hold = "இதோ ஒரு example."
        await processor._flush_hold(FrameDirection.DOWNSTREAM)
        processor._hold = "அப்பா அந்த value சரி."
        await processor._flush_hold(FrameDirection.DOWNSTREAM)

    asyncio.run(run())

    joined = "".join(pushed)
    assert "example.அப்பா" not in joined
    assert "example. அப்பா" in joined


# ── 6 / 19. the per-turn directive must be the last thing the model reads ──

class _Context:
    def __init__(self, messages):
        self._messages = list(messages)

    def get_messages(self):
        return list(self._messages)

    def set_messages(self, messages):
        self._messages = list(messages)


def test_turn_directive_is_pinned_after_the_newest_turn():
    context = _Context(
        [
            {"role": "system", "content": "persona"},
            {"role": "system", "content": "[TUTOR_TURN] old directive"},
            {"role": "user", "content": "explain in tamil"},
            {"role": "assistant", "content": "an earlier English reply"},
            {"role": "user", "content": "இதை தமிழ்ல சொல்லுங்க"},
        ]
    )
    upsert_context_system_note(context, "[TUTOR_TURN]", "[TUTOR_TURN] new", pin_to_end=True)

    messages = context.get_messages()
    assert messages[-1] == {"role": "system", "content": "[TUTOR_TURN] new"}
    assert sum("[TUTOR_TURN]" in m["content"] for m in messages) == 1
    assert messages[0]["content"] == "persona"


def test_pinned_note_does_not_accumulate_across_turns():
    context = _Context([{"role": "system", "content": "persona"}])
    for turn in range(4):
        upsert_context_system_note(
            context, "[TUTOR_TURN]", f"[TUTOR_TURN] turn {turn}", pin_to_end=True
        )
        context.set_messages(
            context.get_messages() + [{"role": "user", "content": f"q{turn}"}]
        )
    messages = context.get_messages()
    assert sum("[TUTOR_TURN]" in m["content"] for m in messages) == 1


def test_stable_notes_keep_their_position_for_prompt_caching():
    context = _Context(
        [
            {"role": "system", "content": "persona"},
            {"role": "system", "content": "[LEARNING_CONTEXT] slide"},
            {"role": "user", "content": "hi"},
        ]
    )
    upsert_context_system_note(context, "[LEARNING_CONTEXT]", "[LEARNING_CONTEXT] slide 2")
    assert context.get_messages()[1]["content"] == "[LEARNING_CONTEXT] slide 2"


def test_trimming_keeps_the_directive_last_in_a_long_session():
    """The sanitizer used to rebuild the prompt as "all system notes, then history"."""
    from pipecat.processors.aggregators.llm_context import LLMContext

    from processors.context_sanitizer import ContextSanitizerProcessor

    messages = [{"role": "system", "content": "persona"}]
    for turn in range(15):
        messages.append({"role": "user", "content": f"question {turn}"})
        messages.append({"role": "assistant", "content": f"answer {turn}."})
    messages.append({"role": "system", "content": "[TUTOR_TURN] reply in Tamil"})

    context = LLMContext(messages=messages)
    ContextSanitizerProcessor(context)._trim_history()

    trimmed = context.messages
    assert trimmed[0]["content"] == "persona"
    assert trimmed[-1]["content"] == "[TUTOR_TURN] reply in Tamil"
    assert sum(1 for m in trimmed if m.get("role") != "system") == (
        ContextSanitizerProcessor.MAX_HISTORY_MESSAGES
    )
    # Oldest turns go first; the newest turn survives.
    assert not any(m["content"] == "question 0" for m in trimmed)
    assert any(m["content"] == "question 14" for m in trimmed)


def test_language_directive_binds_the_whole_reply():
    for code in ("hi", "ta", "te", "en"):
        lines = " ".join(response_language_directive(code))
        assert "WHOLE reply" in lines
        assert "every sentence" in lines
        # 20. concise — a per-turn instruction, not a second system prompt.
        assert len(lines) < 700, code
