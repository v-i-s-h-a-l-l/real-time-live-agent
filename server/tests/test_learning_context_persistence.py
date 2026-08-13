"""Active learning context must survive sanitizer trim and stay in LLM messages."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402

from processors.context_sanitizer import ContextSanitizerProcessor  # noqa: E402
from processors.session_context import (  # noqa: E402
    _LEARNING_MARKER,
    upsert_context_system_note,
)
from tutor.prompts import TUTOR_TURN_MARKER, get_tutor_system_prompt  # noqa: E402


def test_upsert_writes_into_live_llm_context():
    context = LLMContext(messages=[{"role": "system", "content": get_tutor_system_prompt()}])
    upsert_context_system_note(
        context,
        _LEARNING_MARKER,
        f"{_LEARNING_MARKER} CURRENT ACTIVE LEARNING CONTEXT\n- Section: Euclid's Division Lemma",
    )
    contents = [m.get("content", "") for m in context.get_messages()]
    assert any(_LEARNING_MARKER in c and "Euclid" in c for c in contents if isinstance(c, str))


def test_sanitizer_keeps_learning_context_system_note():
    context = LLMContext(
        messages=[
            {"role": "system", "content": get_tutor_system_prompt()},
            {
                "role": "system",
                "content": f"{_LEARNING_MARKER} CURRENT ACTIVE LEARNING CONTEXT\n- Section: Euclid's Division Lemma",
            },
            {"role": "system", "content": f"{TUTOR_TURN_MARKER} mode=learn"},
        ]
    )
    for i in range(20):
        context.add_message({"role": "user", "content": f"user {i}"})
        context.add_message({"role": "assistant", "content": f"assistant {i}."})

    sanitizer = ContextSanitizerProcessor(context=context)
    sanitizer._prepare_context()

    contents = [m.get("content", "") for m in context.get_messages() if m.get("role") == "system"]
    assert any("Lumina" in c for c in contents if isinstance(c, str))
    assert any(_LEARNING_MARKER in c and "Euclid" in c for c in contents if isinstance(c, str))
    assert any(TUTOR_TURN_MARKER in c for c in contents if isinstance(c, str))
    assert not any("Ministros" in c for c in contents if isinstance(c, str))
