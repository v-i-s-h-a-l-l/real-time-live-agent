"""
call_mute_processor.py — CallMuteProcessor

Tracks whether the user is on a phone/side call.
- When user says they're stepping away / taking a call → mutes pipeline (drops all frames silently)
- While muted → all TranscriptionFrames are silently dropped, no LLM is triggered
- When user says re-engagement phrase → unmutes and lets frames through normally

Place this in the pipeline AFTER stt (TranscriptionFrame) and BEFORE user_aggregator.
"""

import re
from loguru import logger

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    TextFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


# ── Trigger phrases that indicate the user is stepping away ──────────────────

MUTE_PATTERNS = [
    r"\b(getting|got|have|taking|on)\s+a\s+(call|phone call|sec|second|minute)\b",
    r"\bone\s+(sec|second|moment|min|minute)\b",
    r"\bhold\s+on\b",
    r"\bjust\s+a\s+(sec|second|moment|min)\b",
    r"\bstep(ping)?\s+away\b",
    r"\bbrb\b",
    r"\bback\s+in\s+a\s+(bit|sec|moment|minute)\b",
    r"\btalk(ing)?\s+to\s+someone\b",
    r"\bsomeone('s|\s+is)?\s+calling\b",
    r"\bi('ll)?\s+be\s+right\s+back\b",
    r"\bgive\s+me\s+a\s+(sec|second|moment|minute)\b",
]

# ── Re-engagement phrases that bring the bot back ────────────────────────────

UNMUTE_PATTERNS = [
    r"\b(hey|hi|hello|okay|ok)\s*(i'?m?\s*)?(back|here|there|done|free)\b",
    r"\bi'?m?\s*back\b",
    r"\bare\s+you\s+(there|here|still there|still here|listening)\b",
    r"\b(louie|lowie|louey)\s*(are\s+you)?\s*(there|here|back)?\b",  # bot name variants
    r"\bsorry\s+(about\s+that|for\s+that|to\s+keep\s+you)\b",
    r"\bback\s+at\s+it\b",
    r"\bwhere\s+were\s+we\b",
    r"\bstill\s+(there|here|with\s+me)\b",
    r"\byou\s+still\s+(there|here)\b",
    r"\bcan\s+you\s+hear\s+me\b",
    r"\bhello\b",  # alone as a re-check
]

_MUTE_RE = [re.compile(p, re.IGNORECASE) for p in MUTE_PATTERNS]
_UNMUTE_RE = [re.compile(p, re.IGNORECASE) for p in UNMUTE_PATTERNS]


def _matches(text: str, patterns: list) -> bool:
    return any(p.search(text) for p in patterns)


class CallMuteProcessor(FrameProcessor):
    """
    Sits between STT and user_aggregator.

    States
    ------
    unmuted (default) — all frames pass through normally
    muted             — TranscriptionFrames are silently dropped;
                        re-engagement phrases flip back to unmuted and
                        inject a short TTSSpeakFrame to let the user know
                        the bot is back.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._muted = False

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _set_muted(self, reason: str):
        if not self._muted:
            self._muted = True
            logger.info("CallMuteProcessor: MUTED — {}", reason)

    def _set_unmuted(self, reason: str):
        if self._muted:
            self._muted = False
            logger.info("CallMuteProcessor: UNMUTED — {}", reason)

    # ── Frame handler ────────────────────────────────────────────────────────

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not isinstance(frame, TranscriptionFrame):
            # All non-transcription frames (audio, control, etc.) always pass
            await self.push_frame(frame, direction)
            return

        text: str = (frame.text or "").strip()
        if not text:
            await self.push_frame(frame, direction)
            return

        if not self._muted:
            # ── Currently UNMUTED ─────────────────────────────────────────
            if _matches(text, _MUTE_RE):
                self._set_muted(f"trigger='{text}'")
                # Let the frame pass once so the LLM can give a natural
                # acknowledgment ("Sure, take your time!")
                await self.push_frame(frame, direction)
            else:
                await self.push_frame(frame, direction)

        else:
            # ── Currently MUTED ───────────────────────────────────────────
            if _matches(text, _UNMUTE_RE):
                self._set_unmuted(f"re-engagement='{text}'")
                # Push the re-engagement utterance through so the LLM
                # can respond naturally ("Welcome back! Where were we?")
                await self.push_frame(frame, direction)
            else:
                # Silently drop — background call audio
                logger.debug(
                    "CallMuteProcessor: dropped (muted) | text='{}'", text
                )
                # Do NOT push the frame — pipeline stays quiet