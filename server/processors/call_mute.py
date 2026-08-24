"""
call_mute_processor.py — CallMuteProcessor

Tracks whether the user is on a phone/side call.
- When user says they're stepping away / taking a call → mutes pipeline (drops all frames silently)
- While muted → all TranscriptionFrames are silently dropped, no LLM is triggered
- When user says re-engagement phrase → unmutes and lets frames through normally
- Auto-unmutes after CALL_MUTE_TIMEOUT_SECS, or on a substantial lesson utterance

Place this in the pipeline AFTER stt (TranscriptionFrame) and BEFORE user_aggregator.
"""

import re
import time
from collections.abc import Callable

from loguru import logger

import config
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
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
    # "I'm back" / "I am back" / "Im back" / "hey I am back"
    r"\bi\s*(?:'?m|am)\s+back\b",
    r"\b(hey|hi|hello|okay|ok|yo)[,.]?\s+i\s*(?:'?m|am)\s+back\b",
    r"\b(hey|hi|hello|okay|ok)\s*(?:i'?m?\s*)?(back|here|there|done|free)\b",
    # back after / from a call
    r"\bback\s+(?:after|from)\s+(?:the\s+|my\s+|that\s+)?(?:call|phone)\b",
    r"\bafter\s+(?:the\s+|my\s+|that\s+)?(?:call|phone)\b",
    r"\b(?:done|finished)\s+with\s+(?:the\s+|my\s+)?(?:call|phone)\b",
    r"\b(?:call|phone)\s+(?:is\s+)?(?:over|done|finished)\b",
    r"\bare\s+you\s+(there|here|still there|still here|listening)\b",
    r"\bassistant\s*(are\s+you)?\s*(there|here|back)?\b",
    r"\bsorry\s+(about\s+that|for\s+that|to\s+keep\s+you)\b",
    r"\bback\s+at\s+it\b",
    r"\bwhere\s+were\s+we\b",
    r"\bstill\s+(there|here|with\s+me)\b",
    r"\byou\s+still\s+(there|here)\b",
    r"\bcan\s+you\s+hear\s+me\b",
    r"\b(?:i\s+)?(?:am\s+)?(?:back|free|done)\s+now\b",
    r"^\s*(?:hello|hey|hi)\s*[.!]?\s*$",  # bare greeting while muted
]

_MUTE_RE = [re.compile(p, re.IGNORECASE) for p in MUTE_PATTERNS]
_UNMUTE_RE = [re.compile(p, re.IGNORECASE) for p in UNMUTE_PATTERNS]
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_FILLER_WORDS = frozenset(
    {
        "uh",
        "um",
        "umm",
        "uhh",
        "er",
        "ah",
        "hmm",
        "hm",
        "mm",
        "mhm",
        "ok",
        "okay",
        "yeah",
        "yes",
        "yep",
        "no",
        "nope",
        "right",
        "wait",
        "like",
        "so",
    }
)


def _matches(text: str, patterns: list) -> bool:
    return any(p.search(text) for p in patterns)


def _looks_like_lesson_utterance(text: str, *, min_words: int) -> bool:
    """True for a real tutoring turn, not a filler or another hold-on."""
    if _matches(text, _MUTE_RE):
        return False
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if len(words) < min_words:
        return False
    return any(word not in _FILLER_WORDS for word in words)


class CallMuteProcessor(FrameProcessor):
    """
    Sits between STT and user_aggregator.

    States
    ------
    unmuted (default) — all frames pass through normally
    muted             — TranscriptionFrames are silently dropped; a
                        re-engagement phrase, a substantial lesson utterance,
                        or CALL_MUTE_TIMEOUT_SECS flips back to unmuted.
    """

    def __init__(
        self,
        should_skip_mute: Callable[[str], bool] | None = None,
        *,
        now: Callable[[], float] | None = None,
        timeout_secs: float | None = None,
        resume_min_words: int | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._muted = False
        self._muted_at: float | None = None
        self._should_skip_mute = should_skip_mute
        self._now = now or time.monotonic
        self._timeout_secs = (
            float(timeout_secs)
            if timeout_secs is not None
            else float(config.CALL_MUTE_TIMEOUT_SECS)
        )
        self._resume_min_words = (
            resume_min_words
            if resume_min_words is not None
            else config.CALL_MUTE_RESUME_MIN_WORDS
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _set_muted(self, reason: str):
        if not self._muted:
            self._muted = True
            self._muted_at = self._now()
            logger.info("CallMuteProcessor: MUTED — {}", reason)

    def _set_unmuted(self, reason: str):
        if self._muted:
            self._muted = False
            self._muted_at = None
            logger.info("CallMuteProcessor: UNMUTED — {}", reason)

    def _timeout_reached(self) -> bool:
        if not self._muted or self._muted_at is None:
            return False
        return (self._now() - self._muted_at) >= self._timeout_secs

    # ── Frame handler ────────────────────────────────────────────────────────

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if self._timeout_reached():
            self._set_unmuted(f"timeout after {self._timeout_secs}s")

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
            if self._should_skip_mute and self._should_skip_mute(text):
                # Study-break duration answers like "one minute" must not
                # be treated as a phone step-away.
                await self.push_frame(frame, direction)
                return
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
            elif _looks_like_lesson_utterance(
                text, min_words=self._resume_min_words
            ):
                self._set_unmuted(f"lesson utterance='{text}'")
                await self.push_frame(frame, direction)
            else:
                # Silently drop — background call audio
                logger.debug(
                    "CallMuteProcessor: dropped (muted) | text='{}'", text
                )
                # Do NOT push the frame — pipeline stays quiet
