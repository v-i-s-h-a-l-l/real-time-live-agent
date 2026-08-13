"""Unit tests for allowlisted TTS voices."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voices import (  # noqa: E402
    ALLOWED_TTS_VOICES,
    DEFAULT_TTS_VOICE_ID,
    resolve_tts_voice_id,
)


def test_default_voice_is_riya():
    assert DEFAULT_TTS_VOICE_ID == "95d51f79-c397-46f9-b49a-23763d3eaa2d"
    assert resolve_tts_voice_id(None) == DEFAULT_TTS_VOICE_ID
    assert resolve_tts_voice_id("not-a-voice") == DEFAULT_TTS_VOICE_ID


def test_all_five_voices_are_allowlisted():
    assert len(ALLOWED_TTS_VOICES) == 5
    assert resolve_tts_voice_id("96e6974d-57a9-4325-89c8-43f065f8bd95") == (
        "96e6974d-57a9-4325-89c8-43f065f8bd95"
    )
    assert resolve_tts_voice_id("4418bb06-8329-49a1-bb11-53bb64ca0547") == (
        "4418bb06-8329-49a1-bb11-53bb64ca0547"
    )
