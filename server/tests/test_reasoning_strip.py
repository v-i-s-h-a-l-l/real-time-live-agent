"""Reasoning block stripping for Groq Qwen models."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.reasoning_strip import ReasoningStripProcessor, strip_thinking_block  # noqa: E402


def test_strip_thinking_block_removes_tags_and_keeps_reply():
    raw = (
        "<think>planning...</think>\n\n"
        "Hello! Let's look at Euclid's lemma together."
    )
    assert strip_thinking_block(raw) == "Hello! Let's look at Euclid's lemma together."


def test_strip_thinking_block_no_tags_unchanged():
    assert strip_thinking_block("Sure — what's confusing you?") == "Sure — what's confusing you?"


def test_streaming_processor_holds_until_close_tag():
    proc = ReasoningStripProcessor()

    first = proc._strip_chunk("<think>still thinking")
    assert first == ""
    assert proc._carry.startswith("<think>")

    second = proc._strip_chunk(" about fractions</think>Hi there.")
    assert second == "Hi there."
    assert proc._carry == ""
