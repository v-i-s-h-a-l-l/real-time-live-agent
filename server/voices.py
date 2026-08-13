"""Allowlisted Cartesia TTS voices the student can pick."""

from __future__ import annotations

DEFAULT_TTS_VOICE_ID = "95d51f79-c397-46f9-b49a-23763d3eaa2d"

ALLOWED_TTS_VOICES: dict[str, str] = {
    "95d51f79-c397-46f9-b49a-23763d3eaa2d": "Riya",
    "96e6974d-57a9-4325-89c8-43f065f8bd95": "Akshara",
    "4418bb06-8329-49a1-bb11-53bb64ca0547": "Shanti",
    "098fb15d-2597-4186-8b74-25340050b6e7": "Vishal",
    "910fb75e-1d20-4840-ac63-ac6b26a71bdc": "Dev",
}


def resolve_tts_voice_id(voice_id: str | None) -> str:
    """Return an allowlisted voice, or the default Riya voice."""
    if voice_id and voice_id in ALLOWED_TTS_VOICES:
        return voice_id
    return DEFAULT_TTS_VOICE_ID
