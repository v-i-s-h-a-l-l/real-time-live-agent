"""Smoke tests for tutor system prompt / directive markers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tutor.prompts import (  # noqa: E402
    TUTOR_TURN_MARKER,
    get_tutor_system_prompt,
)
from pipeline import get_system_prompt  # noqa: E402


def test_tutor_prompt_is_lumina_not_ministros():
    prompt = get_tutor_system_prompt()
    assert "Lumina" in prompt
    assert "Class 10" in prompt
    assert "Ministros" not in prompt
    assert "mathematics tutor" in prompt.lower()
    assert "APPLICATION DOMAIN" in prompt
    assert "not a bank" in prompt.lower()


def test_tutor_prompt_is_voice_first_not_scripted():
    prompt = get_tutor_system_prompt()
    assert "Great question" in prompt  # as a thing to avoid
    assert "Do not open turns with filler" in prompt or "filler" in prompt.lower()
    assert TUTOR_TURN_MARKER in prompt


def test_tutor_prompt_structures_worked_calculations():
    prompt = get_tutor_system_prompt()
    assert "each equation" in prompt.lower() or "own line" in prompt.lower()
    assert "commas" in prompt.lower()
    assert "English, Hindi, and Tamil" in prompt or "all languages" in prompt.lower()


def test_tutor_prompt_teaches_out_loud_not_symbol_dump():
    prompt = get_tutor_system_prompt()
    assert "TEACH OUT LOUD" in prompt
    assert r"\[" in prompt
    assert "at least zero" in prompt.lower() or "smaller than b" in prompt.lower()
    assert "$$" in prompt
    assert "BAD" in prompt and "GOOD" in prompt


def test_explain_directive_reminds_to_teach_out_loud():
    from tutor.engine import TutorEngine
    from tutor.types import TutorState
    from tutor.prompts import build_tutor_turn_directive

    engine = TutorEngine()
    state = TutorState(phase="learning")
    decision = engine.decide("What is Euclid's division lemma?", state)
    directive = build_tutor_turn_directive(
        decision=decision,
        state=state,
        learning_context=None,
        tutor_context=None,
        utterance="What is Euclid's division lemma?",
    )
    assert "Teach out loud" in directive
    assert "inequalities in words" in directive


def test_pipeline_prompt_delegates_to_tutor():
    assert "Lumina" in get_system_prompt()
    assert TUTOR_TURN_MARKER in get_tutor_system_prompt()


def _directive_for(active_language):
    from tutor.engine import TutorEngine
    from tutor.types import TutorState
    from tutor.prompts import build_tutor_turn_directive

    engine = TutorEngine()
    state = TutorState(phase="learning")
    utterance = "इस slide को समझाओ"
    decision = engine.decide(utterance, state)
    return build_tutor_turn_directive(
        decision=decision,
        state=state,
        learning_context=None,
        tutor_context=None,
        utterance=utterance,
        active_language=active_language,
    )


def test_directive_reasserts_active_language_every_turn():
    # The core fix: the per-turn directive names the reply language, so the
    # student's spoken language wins over the English slide / prior English reply.
    hi = _directive_for("hi-IN")
    assert "Reply language: Hindi" in hi
    assert "Hinglish" in hi
    assert "ONLY signal for reply" in hi

    ta = _directive_for("ta-IN")
    assert "Reply language: Tamil" in ta
    assert "Tanglish" in ta

    te = _directive_for("te-IN")
    assert "Reply language: Telugu" in te
    assert "Tenglish" in te

    en = _directive_for("en-IN")
    assert "Reply language: English" in en


def test_directive_language_defaults_to_english_when_unknown():
    d = _directive_for(None)
    assert "Reply language: English" in d


def test_indic_directive_warns_against_one_english_word_switch():
    d = _directive_for("hi-IN")
    assert "One English maths word does not make the turn English" in d


def test_system_prompt_language_policy_is_explicit():
    prompt = get_tutor_system_prompt()
    assert "Tamil/Tanglish" in prompt
    assert "Telugu/Tenglish" in prompt
    assert "One English word does not make the turn English" in prompt
