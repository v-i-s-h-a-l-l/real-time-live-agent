"""Opening greeting copy is part of the student-facing first turn."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opening import opening_system_message  # noqa: E402
from processors.session_context import SessionContextStore  # noqa: E402

_MATCH = "After they speak, always match their language (English, Hindi, Tamil, or Telugu)."


def test_generic_greeting_when_no_curriculum_has_arrived():
    store = SessionContextStore()
    message = opening_system_message(store)
    assert "Class 10 maths tutoring session" in message
    assert "Lumina" in message
    assert _MATCH in message
    assert "The topic is" not in message


def test_topic_greeting_uses_title_not_id():
    store = SessionContextStore()
    store.set_context({"topicId": "real-numbers", "topicTitle": "Real Numbers"})
    message = opening_system_message(store)
    assert "on 'Real Numbers'" in message
    assert "real-numbers" not in message
    assert "slide" not in message


def test_slide_greeting_names_topic_and_section():
    store = SessionContextStore()
    store.set_context({"topicTitle": "Real Numbers"})
    store.set_learning_context({"sectionTitle": "Euclid's Division Lemma"})
    message = opening_system_message(store)
    assert "The topic is 'Real Numbers'" in message
    assert "slide 'Euclid's Division Lemma'" in message
    assert _MATCH in message
