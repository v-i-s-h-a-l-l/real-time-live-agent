"""Extract the latest user utterance from LLM chat messages."""

from __future__ import annotations

from typing import Any


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            text = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )
        else:
            text = str(content or "")
        text = text.strip()
        if text:
            return text
    return ""
