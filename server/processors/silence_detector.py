"""
SilenceDetectorProcessor
────────────────────────
Detects when the user goes silent mid-conversation and then returns.

Tracks the elapsed time between the last UserStoppedSpeakingFrame and the
next UserStartedSpeakingFrame. When the gap exceeds `silence_threshold_secs`,
it injects a `[USER_RETURNED_AFTER_SILENCE]` system message into the LLM
context so the model can re-anchor the conversation naturally.

Three tiers:
  SHORT  — 15s to 2min  : pick up naturally with one anchor line
  MEDIUM — 2min to 5min : soft reminder + ask if they want to continue
  LONG   — > 5min       : context is stale, open fresh

Place this AFTER stt and BEFORE the user_aggregator in the pipeline.
"""

import time

from loguru import logger

from pipecat.frames.frames import (
    Frame,
    LLMMessagesAppendFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SilenceDetectorProcessor(FrameProcessor):
    """
    Inject a gap-tier-aware system message when the user returns after silence.

    Args:
        silence_threshold_secs:
            Minimum gap to trigger any silence signal. Default: 15s.
        medium_silence_threshold_secs:
            Gap at which context is getting stale. Default: 120s (2min).
        long_silence_threshold_secs:
            Gap at which context is fully stale — open fresh. Default: 300s (5min).
    """

    def __init__(
        self,
        *,
        silence_threshold_secs: float = 15.0,
        medium_silence_threshold_secs: float = 120.0,
        long_silence_threshold_secs: float = 300.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._silence_threshold = silence_threshold_secs
        self._medium_silence_threshold = medium_silence_threshold_secs
        self._long_silence_threshold = long_silence_threshold_secs

        self._last_stop_ts: float | None = None
        self._silence_detected = False
        self._silence_duration: float = 0.0
        self._turn_count: int = 0

        logger.info(
            "[SilenceDetector] Initialized | short={}s medium={}s long={}s",
            self._silence_threshold,
            self._medium_silence_threshold,
            self._long_silence_threshold,
        )

    def _classify_gap(self, gap: float) -> str:
        if gap >= self._long_silence_threshold:
            return "long"
        if gap >= self._medium_silence_threshold:
            return "medium"
        return "short"

    def _build_hint(self, gap: float, tier: str) -> dict:
        minutes = int(gap // 60)
        seconds = int(gap % 60)

        if minutes > 0:
            gap_str = f"{minutes} minute{'s' if minutes > 1 else ''} and {seconds} seconds" if seconds else f"{minutes} minute{'s' if minutes > 1 else ''}"
        else:
            gap_str = f"{seconds} seconds"

        if tier == "short":
            content = (
                f"[USER_RETURNED_AFTER_SILENCE | gap={gap_str} | tier=short] "
                "The user briefly went silent and just came back. "
                "Start with ONE short natural sentence that recalls where you left off. "
                "Then ask what they want next — one question only. "
                "Do NOT mention the silence. Do NOT summarize the whole conversation."
            )
        elif tier == "medium":
            content = (
                f"[USER_RETURNED_AFTER_SILENCE | gap={gap_str} | tier=medium] "
                "The user has been away for a few minutes and just returned. "
                "They may have forgotten where you were. "
                "Give a soft one-sentence reminder of the last topic and ask if they want to continue or need something else. "
                "Keep it casual and brief — one sentence, one question."
            )
        else:  # long
            content = (
                f"[USER_RETURNED_AFTER_SILENCE | gap={gap_str} | tier=long] "
                "The user has been away for a long time. The previous context is stale. "
                "Do NOT reference what was discussed before. "
                "Open fresh — greet them naturally with something like 'Hey, good to have you back. What can I help you with?' "
                "One sentence only."
            )

        return {"role": "system", "content": content}

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # ── User stopped speaking → record timestamp ─────────────────────
        if isinstance(frame, UserStoppedSpeakingFrame):
            self._last_stop_ts = time.monotonic()
            await self.push_frame(frame, direction)
            return

        # ── User started speaking → check for silence gap ────────────────
        if isinstance(frame, UserStartedSpeakingFrame):
            self._turn_count += 1
            self._silence_detected = False

            if self._last_stop_ts is not None and self._turn_count > 1:
                gap = time.monotonic() - self._last_stop_ts
                if gap >= self._silence_threshold:
                    self._silence_detected = True
                    self._silence_duration = gap
                    tier = self._classify_gap(gap)
                    logger.info(
                        "[SilenceDetector] User returned after {:.1f}s | tier={}",
                        gap,
                        tier,
                    )

            await self.push_frame(frame, direction)
            return

        # ── LLMMessagesAppendFrame → inject silence hint if detected ─────
        if isinstance(frame, LLMMessagesAppendFrame):
            if self._silence_detected:
                self._silence_detected = False  # consume the flag

                gap = self._silence_duration
                tier = self._classify_gap(gap)
                hint = self._build_hint(gap, tier)

                # Insert just before the last message (the user's new utterance)
                messages = list(frame.messages)
                if len(messages) > 0:
                    messages.insert(-1, hint)
                else:
                    messages.append(hint)

                frame = LLMMessagesAppendFrame(messages=messages)

                logger.info(
                    "[SilenceDetector] Injected hint | gap={:.0f}s tier={}",
                    gap,
                    tier,
                )

            await self.push_frame(frame, direction)
            return

        # ── Everything else passes through ───────────────────────────────
        await self.push_frame(frame, direction)