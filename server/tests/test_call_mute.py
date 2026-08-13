"""Tests for CallMute unmute / re-engagement phrases."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.call_mute import _UNMUTE_RE, _MUTE_RE, _matches  # noqa: E402


def test_unmute_i_am_back():
    assert _matches("hey I am back after call", _UNMUTE_RE)
    assert _matches("hey I'm back", _UNMUTE_RE)
    assert _matches("I am back", _UNMUTE_RE)
    assert _matches("I'm back now", _UNMUTE_RE)
    assert _matches("Im back", _UNMUTE_RE)


def test_unmute_after_call_phrases():
    assert _matches("back after the call", _UNMUTE_RE)
    assert _matches("hey I am back after call to the voice assistant", _UNMUTE_RE)
    assert _matches("done with the call", _UNMUTE_RE)
    assert _matches("the call is over", _UNMUTE_RE)
    assert _matches("I am back now", _UNMUTE_RE)


def test_unmute_presence_checks():
    assert _matches("are you there", _UNMUTE_RE)
    assert _matches("can you hear me", _UNMUTE_RE)
    assert _matches("hello", _UNMUTE_RE)


def test_mute_still_triggers_on_step_away():
    assert _matches("I am taking a call", _MUTE_RE)
    assert _matches("one second", _MUTE_RE)
    assert _matches("hold on", _MUTE_RE)


def test_study_break_skip_prevents_one_minute_mute():
    from processors.call_mute import CallMuteProcessor

    processor = CallMuteProcessor(should_skip_mute=lambda text: "minute" in text.lower())
    assert processor._should_skip_mute is not None
    assert processor._should_skip_mute("one minute")
    assert not processor._muted
