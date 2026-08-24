"""Shared last-user-utterance helper used by several processors."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.llm_context_text import _last_user_text  # noqa: E402


def test_plain_string_content():
    assert _last_user_text(
        [
            {"role": "system", "content": "Lumina"},
            {"role": "user", "content": "Explain this."},
        ]
    ) == "Explain this."


def test_walks_backward_past_assistant():
    assert _last_user_text(
        [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "still going"},
        ]
    ) == "second"


def test_skips_empty_and_whitespace_user_turns():
    assert _last_user_text(
        [
            {"role": "user", "content": "keep me"},
            {"role": "user", "content": ""},
            {"role": "user", "content": "   "},
            {"role": "user", "content": None},
        ]
    ) == "keep me"


def test_multipart_text_parts_are_joined():
    assert _last_user_text(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image", "url": "x"},
                    {"type": "text", "text": "world"},
                ],
            }
        ]
    ) == "hello world"


def test_strips_plain_and_multipart_text():
    assert _last_user_text([{"role": "user", "content": "  padded  "}]) == "padded"
    assert (
        _last_user_text(
            [{"role": "user", "content": [{"type": "text", "text": "  a  "}]}]
        )
        == "a"
    )


def test_empty_or_no_user_returns_blank():
    assert _last_user_text([]) == ""
    assert _last_user_text([{"role": "assistant", "content": "hi"}]) == ""
    assert _last_user_text([{"role": "user", "content": [{"type": "image"}]}]) == ""
