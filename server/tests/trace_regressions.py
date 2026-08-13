"""Dev-only trace: STT text → language state → LLM instruction → TTS text → TTS language.

Run:  python tests/trace_regressions.py
Not part of the pytest suite; it prints the pipeline boundaries for manual review.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from languages import detect_language_request, resolve_detected_language, to_cartesia_language
from processors.naturalizer import ResponseNaturalizerProcessor
from processors.speak_math import speak_for_tts
from tutor.prompts import response_language_directive


def trace(label: str, stt: str, sarvam: str | None, active: str, llm_output: str) -> None:
    requested = detect_language_request(stt)
    detected, confidence, source = resolve_detected_language(
        text=stt, sarvam_language=sarvam, min_chars=8, min_confidence=0.55
    )
    final = requested or detected or active
    naturalizer = ResponseNaturalizerProcessor(
        add_starters=False, get_language=lambda: final
    )
    tts_text = naturalizer._clean(llm_output)

    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")
    print(f"1 STT output            : {stt}")
    print(f"2 detected language     : {detected} (conf={confidence:.2f} source={source})")
    print(f"  explicit request      : {requested or '-'}")
    print(f"3 active language state : {active} -> {final}")
    print("5 language instruction  :")
    for line in response_language_directive(final):
        print(f"    {line}")
    print(f"6 raw LLM output        : {llm_output}")
    print(f"9 final TTS input       : {tts_text}")
    print(f"10 TTS language         : {to_cartesia_language(final)}")


if __name__ == "__main__":
    trace(
        "HINDI — whole-slide explanation with maths",
        "इस पूरे concept को हिंदी में समझाओ",
        "hi-IN",
        "en",
        "हाँ, चलो इसे step by step समझते हैं. सबसे पहले equation $2x + 3y = 12$ लो, "
        "फिर $y$ की value निकालो.",
    )
    trace(
        "TAMIL — explicit request mid-English session",
        "இந்த concept-ஐ தமிழ்ல explain பண்ணுங்க",
        "ta-IN",
        "en",
        "சரி, இதை simple-ஆ பாப்போம். இந்த equation-ல $x = 2y + 3$ னு substitute பண்ணுங்க.",
    )
    trace(
        "ENGLISH — maths pronunciation must stay natural",
        "Explain this entire concept in English",
        "en-IN",
        "ta",
        "Sure. Take $2x^2 + 5x + 3 = 0$, and remember the remainder $r$ satisfies "
        r"$0 \leq r < b$. The sum of the zeros is $\alpha + \beta = -b/a$.",
    )
    trace(
        "PERSISTENCE — short English filler must not flip Hindi",
        "okay",
        None,
        "hi",
        "ठीक है, अब अगला step देखते हैं.",
    )
    trace(
        "LATEX ENVIRONMENT — cases block must not be spelled out",
        "इसको solve करो",
        "hi-IN",
        "hi",
        r"चलो solve करते हैं: \[ \begin{cases} 2x + 3y = 12 \\ x - y = 1 \end{cases} \]",
    )
