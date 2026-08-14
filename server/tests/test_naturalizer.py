"""Naturalizer: speech-friendly maths and robotic preamble stripping."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.naturalizer import ResponseNaturalizerProcessor  # noqa: E402


def _clean(text: str) -> str:
    return ResponseNaturalizerProcessor._clean(
        ResponseNaturalizerProcessor(add_starters=False),
        text,
    )


def test_strips_sure_and_great_question():
    assert _clean("Sure! b is 5.") == "b is five."
    assert _clean("Great question! The discriminant is b squared minus 4ac.") == (
        "The discriminant is b squared minus 4ac."
    )


def test_strips_awesome_fantastic():
    assert _clean("Awesome! You've got it.") == "You've got it."
    assert _clean("Fantastic! Let's try the next one.") == "Let's try the next one."


def test_math_symbols_become_speech():
    spoken = _clean("x = (-b ± √(b² - 4ac)) / 2a")
    low = spoken.lower()
    assert "plus or minus" in low
    assert "square root of" in low
    assert "squared" in low
    assert "equals" in low
    assert "±" not in spoken
    assert "√" not in spoken
    assert "²" not in spoken
    assert "<break" not in spoken


def test_preserves_single_underscore_in_identifiers():
    spoken = _clean("a_n is the nth term.")
    assert "underscore" not in spoken.lower()
    assert "sub" in spoken or "a_n" in spoken


def test_latex_delimiters_become_speech_not_dollar_signs():
    from processors.naturalizer import speak_latex, speak_math_delimiters

    spoken = speak_latex(r"\frac{-b \pm \sqrt{b^2-4ac}}{2a}")
    assert "dollar" not in spoken.lower()
    assert "plus or minus" in spoken
    assert "square root of" in spoken
    assert "divided by" in spoken or "over" in spoken

    cleaned = _clean(r"The formula is $$\frac{-b \pm \sqrt{b^2-4ac}}{2a}$$ here.")
    assert "$$" not in cleaned
    assert "$" not in cleaned
    assert "plus or minus" in cleaned.lower()
    assert speak_math_delimiters("it is $x^2$") != "$x^2$"
    assert "squared" in speak_math_delimiters("it is $x^2$")
    assert "squared" in speak_math_delimiters("$x^2$")


def test_newlines_between_steps_become_spoken_pauses():
    from processors.naturalizer import speak_newlines

    stepped = (
        "Let's try 84 and 30:\n"
        "84 = 30 × 2 + 24\n"
        "30 = 24 × 1 + 6\n"
        "24 = 6 × 4 + 0\n"
        "so the HCF is 6."
    )
    spoken = speak_newlines(stepped)
    assert "\n" not in spoken
    assert "new line" not in spoken.lower()
    assert "84 = 30" in spoken
    assert ". 30 = 24" in spoken or ".  30 = 24" in spoken
    cleaned = _clean(stepped)
    assert "\n" not in cleaned
    assert "84" in cleaned or "eighty-four" in cleaned
    assert "equals" in cleaned


def test_inequalities_are_spoken_not_stripped():
    from processors.naturalizer import speak_math_delimiters

    for source in (
        "0 < r < b",
        r"where $0 \leq r < b$.",
        r"where $0 \le r < b$.",
        "0 ≤ r < b",
        r"where $0 \leq 9 < 13$.",
    ):
        spoken = speak_math_delimiters(source)
        cleaned = _clean(source)
        for text in (spoken, cleaned):
            assert "<" not in text
            assert "≤" not in text
            assert "less than" in text
            collapsed = " ".join(text.split())
            assert "0 r b" not in collapsed


def test_bracket_display_math_is_spoken_not_read_as_latex():
    spoken = _clean(r"we can write \[ a = bq + r \] where q is the quotient.")
    assert r"\[" not in spoken
    assert r"\]" not in spoken
    assert "equals" in spoken
    assert "times" in spoken


def test_does_not_strip_natural_ack():
    assert _clean("Yeah.") == "Yeah."
    assert _clean("Exactly. That's the idea.") == "Exactly. That's the idea."


def test_number_minute_hyphen_is_not_minus_on_tts_path():
    spoken = _clean("Take a 20-minute focused session, then a 5-minute break.")
    assert spoken == (
        "Take a twenty-minute focused session, then a five-minute break."
    )
    assert "minus" not in spoken
    math = _clean("Then compute 5 - 2 and -5.")
    assert "minus" in math
    assert "negative five" in math
