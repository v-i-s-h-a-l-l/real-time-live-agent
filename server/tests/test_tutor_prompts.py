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


def _directive_for(active_language, reply_script=None):
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
        reply_script=reply_script,
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


def test_system_prompt_does_not_quote_refusal_lines():
    prompt = get_tutor_system_prompt().lower()
    assert "that's outside our lesson" not in prompt
    assert "let's stay on topic" not in prompt
    assert "if mode is redirect" not in prompt
    assert "grant_pause" in prompt
    assert "acknowledge_and_steer" not in prompt


def test_system_prompt_has_session_engagement_and_break_rules():
    prompt = get_tutor_system_prompt()
    assert "NO SELF-INTRODUCTION AFTER THE FIRST TURN" in prompt
    assert "BREAKS CAN ALWAYS BE ENDED EARLY" in prompt
    assert "AFTER A TRANSITION IS CONFIRMED" in prompt
    assert "REINFORCE ENGAGEMENT" in prompt
    assert "KEEP SMALL TALK BRIEF" in prompt
    assert "VERIFY MATH BEFORE LABELING" in prompt
    assert "DELIVER IT IMMEDIATELY" in prompt
    assert "TARGET THE SPECIFIC POINT OF CONFUSION" in prompt
    assert "LANGUAGE SWITCHES ARE STICKY" in prompt
    assert "MATCH THE STUDENT'S SCRIPT" in prompt
    assert "RELIABLY DETECT LANGUAGE-CAPABILITY QUESTIONS" in prompt
    assert "NEVER USE \"WELCOME BACK\"" in prompt
    assert "IF A MESSAGE'S INTENT IS UNCLEAR" in prompt
    assert "SCRIPT MATCHING MUST BE APPLIED CONSISTENTLY" in prompt
    assert "CLEAR LANGUAGE SWITCH" in prompt
    assert "STRUGGLE SIGNALS" in prompt
    assert "START FROM SOMETHING THE STUDENT ALREADY KNOWS" in prompt
    assert "BREAK NEW CONCEPTS INTO SMALL SEQUENTIAL PIECES" in prompt
    assert "SIMPLE, EVERYDAY WORDS BEFORE INTRODUCING TECHNICAL TERMS" in prompt
    assert "CHECK UNDERSTANDING BEFORE MOVING FORWARD" in prompt
    assert "USE VISUAL/PHYSICAL LANGUAGE" in prompt
    assert "FIRST-TIME CONCEPT INTRODUCTION AND SLIDE" in prompt
    assert "DOES NOT REPLACE EXISTING BORING/CONFUSING-RESPONSE BEHAVIOR" in prompt


def test_directive_language_is_sticky_and_names_script():
    hi = _directive_for("hi-IN")
    assert "Session language is STICKY" in hi
    assert "Roman/Latin" in hi
    assert "Do NOT use Devanagari" in hi

    ta_native = _directive_for("ta-IN", reply_script="native")
    assert "Tamil script" in ta_native
    assert "Do not switch to Roman/Latin" in ta_native
