"""Per-turn context scope must match the chosen steer action.

Three modes:

* WITHHELD — pure student-state turns (grant_pause / grant_leave / joke_beat).
  No lesson identity in the system messages at all. The reply is about the
  student.
* SCOPE-ONLY — scope-holding turns (hold_scope / hold_firm / defer_light /
  finish_then_pause). Topic and section stay visible so the tutor can redirect
  ("we're on Euclid's Division Lemma, that's later"), but visible content and
  formulas are stripped so it does not also teach.
* FULL — teaching turns and resume_lesson. The whole learning context is
  restored so the tutor can actually teach.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402

from processors.session_context import (  # noqa: E402
    _LEARNING_MARKER,
    _SESSION_MARKER,
    SessionContextStore,
    upsert_context_system_note,
)
from processors.tutor_turn import TutorTurnProcessor  # noqa: E402
from tutor.prompts import TUTOR_TURN_MARKER, get_tutor_system_prompt  # noqa: E402


LESSON_LEARNING_CONTEXT = {
    "phase": "learning",
    "classLabel": "Class 10",
    "subjectName": "Mathematics",
    "chapterTitle": "Real Numbers",
    "topicTitle": "Euclid's Division Lemma",
    "sectionTitle": "About Euclid's Division Lemma",
    "visibleContent": "For any two positive integers a and b, a = bq + r, 0 <= r < b.",
    "formulas": ["a = bq + r"],
}

LESSON_SESSION_CONTEXT = {
    "classLabel": "Class 10",
    "subjectName": "Mathematics",
    "chapterTitle": "Real Numbers",
    "topicTitle": "Euclid's Division Lemma",
}


def _build_processor() -> tuple[TutorTurnProcessor, LLMContext, SessionContextStore]:
    store = SessionContextStore()
    store.set_context(LESSON_SESSION_CONTEXT)
    store.set_learning_context(LESSON_LEARNING_CONTEXT)

    llm_context = LLMContext(
        messages=[{"role": "system", "content": get_tutor_system_prompt()}]
    )
    # Prime the persistent context notes exactly the way SessionContextProcessor
    # would after receiving them from the client.
    from processors.session_context import _learning_note, _system_note

    upsert_context_system_note(
        llm_context, _SESSION_MARKER, _system_note(LESSON_SESSION_CONTEXT)
    )
    upsert_context_system_note(
        llm_context, _LEARNING_MARKER, _learning_note(LESSON_LEARNING_CONTEXT)
    )

    processor = TutorTurnProcessor(
        store=store,
        llm_context=llm_context,
        session_id="test-session",
    )
    return processor, llm_context, store


def _system_content(llm_context: LLMContext, marker: str) -> str:
    for message in llm_context.get_messages():
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str) and marker in content:
            return content
    raise AssertionError(f"{marker} note missing from context")


def _apply(processor: TutorTurnProcessor, llm_context: LLMContext, utterance: str) -> None:
    llm_context.add_message({"role": "user", "content": utterance})
    processor._apply_tutor_turn()


def _assert_no_slide_content(text: str) -> None:
    """Content that must never leak into a redirect or student-state reply."""
    assert "a = bq + r" not in text
    assert "For any two positive integers" not in text
    # Ground-answers-in-this-unit tail must be gone in both scoped and withheld.
    assert "Move Next" not in text
    assert "move Next" not in text


def test_hungry_turn_fully_withholds_lesson_context():
    processor, llm_context, _store = _build_processor()

    _apply(processor, llm_context, "I am hungry")

    learning = _system_content(llm_context, _LEARNING_MARKER)
    session = _system_content(llm_context, _SESSION_MARKER)
    # Pure student-state — no lesson identity at all.
    for banned in (
        "Euclid",
        "Division Lemma",
        "About Euclid",
        "Real Numbers",
        "Class 10",
        "Mathematics",
    ):
        assert banned not in learning, f"[LEARNING_CONTEXT] still names {banned!r}"
        assert banned not in session, f"[SESSION_CONTEXT] still names {banned!r}"
    assert "withheld" in learning.lower()
    assert "withheld" in session.lower()


def test_movie_turn_keeps_topic_anchor_but_drops_slide_and_formula():
    processor, llm_context, _store = _build_processor()

    _apply(processor, llm_context, "Movie")

    learning = _system_content(llm_context, _LEARNING_MARKER)
    session = _system_content(llm_context, _SESSION_MARKER)
    # Scope-only — the redirect needs to name what we're on.
    assert "Euclid's Division Lemma" in learning
    assert "About Euclid's Division Lemma" in learning
    assert "Real Numbers" in session
    _assert_no_slide_content(learning)
    assert "Scope frame only" in learning
    assert "Scope frame only" in session


def test_who_is_cm_of_tn_holds_scope_with_topic_anchor():
    processor, llm_context, _store = _build_processor()

    _apply(processor, llm_context, "Who is the CM of Tamil Nadu?")

    learning = _system_content(llm_context, _LEARNING_MARKER)
    # This is the whole point: the LLM must still know the topic so it can
    # say "we're on Euclid's Division Lemma, that's later" — but it must not
    # have the formula or slide text to also teach the concept.
    assert "Euclid's Division Lemma" in learning
    _assert_no_slide_content(learning)


def test_deviate_the_topic_holds_scope_with_topic_anchor():
    processor, llm_context, _store = _build_processor()

    _apply(processor, llm_context, "Deviate the topic")

    learning = _system_content(llm_context, _LEARNING_MARKER)
    assert "Euclid's Division Lemma" in learning
    _assert_no_slide_content(learning)


def test_teaching_turn_keeps_full_learning_context():
    processor, llm_context, _store = _build_processor()

    _apply(processor, llm_context, "Explain the lemma.")

    learning = _system_content(llm_context, _LEARNING_MARKER)
    assert "Euclid's Division Lemma" in learning
    assert "a = bq + r" in learning
    assert "withheld" not in learning.lower()
    assert "Scope frame only" not in learning


def test_conversational_then_teaching_restores_context():
    processor, llm_context, _store = _build_processor()

    _apply(processor, llm_context, "I am hungry")
    learning_conv = _system_content(llm_context, _LEARNING_MARKER)
    assert "withheld" in learning_conv.lower()

    _apply(processor, llm_context, "What does a = bq + r mean?")
    learning_teach = _system_content(llm_context, _LEARNING_MARKER)
    assert "Euclid's Division Lemma" in learning_teach
    assert "a = bq + r" in learning_teach
    assert "withheld" not in learning_teach.lower()


def test_return_utterance_after_pause_restores_lesson_context():
    processor, llm_context, _store = _build_processor()

    _apply(processor, llm_context, "I am hungry")
    assert "withheld" in _system_content(llm_context, _LEARNING_MARKER).lower()
    assert processor.state.awaiting_return is True

    _apply(processor, llm_context, "I'm back")
    restored = _system_content(llm_context, _LEARNING_MARKER)
    assert "Euclid's Division Lemma" in restored
    assert "withheld" not in restored.lower()
    assert "Scope frame only" not in restored
