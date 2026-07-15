"""
LLMEmptyGuardProcessor
──────────────────────
Detects when the LLM produces an empty response (no TextFrames) and
injects a fallback message to keep the conversation going.

Also enforces a max-wait timeout: if the LLM hasn't produced any text
within `timeout_secs` of starting, the fallback fires immediately
instead of waiting for LLMFullResponseEndFrame.

Two fallback pools:
  - TIMEOUT fallbacks: used when the LLM is slow/unresponsive (don't
    blame the user — it's the system's fault)
  - EMPTY fallbacks: used when the LLM returns but with no content
    (likely the user's input was unclear)
"""

import asyncio
import random

from loguru import logger

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TextFrame,
    UserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


# Timeout fallbacks — LLM was too slow, don't blame the user
TIMEOUT_FALLBACKS = [
    "hang on, let me think about that",
    "one sec, I'm working on that",
    "give me a moment",
    "hold on, still processing",
    "just a sec",
]

# Empty fallbacks — LLM returned empty. Keep these light and natural, and don't
# lean on "sorry" every time (over-apologizing sounds robotic).
EMPTY_FALLBACKS = [
    "sorry, could you say that again?",
    "hmm, one more time?",
    "I didn't quite catch that — go on",
    "wait, say that again?",
    "you were saying?",
    "mind repeating that?",
    "gotcha — what was that again?",
]

# Escalation line — used after several empty responses in a row so the user
# never gets stuck hearing "say that again?" on a loop.
ESCALATION_FALLBACK = (
    "I'm having a bit of trouble on my end. Can you tell me in a few words what you need?"
)

# After this many consecutive empty responses, switch to the escalation line.
_ESCALATION_AFTER = 3

# Sentinel emitted by the LLM for background conversations.
# When the naturalizer swallows this, the response appears empty —
# but we must NOT inject a fallback in that case.
_BACKGROUND_SENTINEL = "[BACKGROUND]"


class LLMEmptyGuardProcessor(FrameProcessor):
    """
    Injects a fallback TextFrame when the LLM produces an empty response.
    Rotates through a list of fallback messages so the user never hears
    the same phrase twice in a row.

    Also starts a timer when the LLM begins processing. If no TextFrame
    arrives within `timeout_secs`, the fallback fires immediately —
    preventing long silences when the LLM is slow or rate-limited.

    Suppresses fallback injection when the LLM responded with [BACKGROUND]
    (background conversation detected — silence is the correct behaviour).

    Args:
        empty_fallbacks:   Fallback strings for empty LLM responses.
        timeout_fallbacks: Fallback strings for LLM timeouts.
        timeout_secs:      Max seconds to wait for first TextFrame after
                           LLMFullResponseStartFrame before injecting fallback.
    """

    def __init__(
        self,
        empty_fallbacks: list[str] | None = None,
        timeout_fallbacks: list[str] | None = None,
        timeout_secs: float = 4.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._empty_fallbacks = empty_fallbacks or EMPTY_FALLBACKS
        self._timeout_fallbacks = timeout_fallbacks or TIMEOUT_FALLBACKS
        self._timeout_secs = timeout_secs
        self._last_empty_index: int = -1
        self._last_timeout_index: int = -1
        self._has_text = False
        self._interrupted = False
        self._timeout_fired = False
        self._is_background = False  # True when LLM said [BACKGROUND]
        self._timeout_task: asyncio.Task | None = None
        self._consecutive_empties = 0
        logger.info(
            "[LLMEmptyGuard] Initialized | {} empty + {} timeout fallbacks | timeout={}s",
            len(self._empty_fallbacks),
            len(self._timeout_fallbacks),
            timeout_secs,
        )

    def _pick_fallback(self, pool: list[str], last_attr: str) -> str:
        """Pick a random fallback from a pool, never repeating the last one."""
        last_index = getattr(self, last_attr, -1)
        available = [(i, t) for i, t in enumerate(pool) if i != last_index]
        index, text = random.choice(available)
        setattr(self, last_attr, index)
        return text

    def _cancel_timeout(self):
        """Cancel any pending timeout task."""
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            self._timeout_task = None

    async def _on_timeout(self):
        """Fires when the LLM hasn't produced text within timeout_secs."""
        try:
            await asyncio.sleep(self._timeout_secs)
        except asyncio.CancelledError:
            return

        # Timer expired and no text arrived — inject timeout fallback
        # but NOT if this was a background detection turn
        if not self._has_text and not self._interrupted and not self._is_background:
            self._timeout_fired = True
            fallback = self._pick_fallback(
                self._timeout_fallbacks, "_last_timeout_index"
            )
            logger.warning(
                "[LLMEmptyGuard] LLM timeout ({}s) — injecting: '{}'",
                self._timeout_secs,
                fallback,
            )
            await self.push_frame(
                TextFrame(text=fallback),
                FrameDirection.DOWNSTREAM,
            )
            await self.push_frame(
                LLMFullResponseEndFrame(),
                FrameDirection.DOWNSTREAM,
            )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            # LLM just started — reset state and start the timeout clock
            self._has_text = False
            self._interrupted = False
            self._timeout_fired = False
            self._is_background = False
            self._cancel_timeout()
            self._timeout_task = asyncio.create_task(self._on_timeout())
            await self.push_frame(frame, direction)

        elif isinstance(frame, TextFrame):
            # Check if this is the [BACKGROUND] sentinel before it's cleaned
            if frame.text.strip() == _BACKGROUND_SENTINEL:
                # Mark as background — suppress all fallbacks for this turn
                self._is_background = True
                self._cancel_timeout()
                logger.debug("[LLMEmptyGuard] [BACKGROUND] detected — suppressing fallback")
                # Drop the sentinel entirely — it must NEVER reach TTS, or the
                # bot would literally say "background".
                return

            self._has_text = True
            self._consecutive_empties = 0  # reset streak
            self._cancel_timeout()  # Got text — no need for timeout
            if not self._timeout_fired:
                await self.push_frame(frame, direction)
            # If timeout already fired, silently drop late-arriving text
            # to avoid double-speaking

        elif isinstance(frame, LLMFullResponseEndFrame):
            self._cancel_timeout()
            if not self._has_text and not self._interrupted and not self._timeout_fired:
                if self._is_background:
                    # LLM said [BACKGROUND] — silence is correct, no fallback
                    logger.debug(
                        "[LLMEmptyGuard] Empty response was [BACKGROUND] — suppressed fallback"
                    )
                else:
                    # Genuinely empty — inject fallback
                    self._consecutive_empties += 1
                    if self._consecutive_empties >= _ESCALATION_AFTER:
                        # Too many empties in a row — stop asking them to repeat
                        # and take ownership of the problem instead.
                        fallback = ESCALATION_FALLBACK
                        self._consecutive_empties = 0
                    else:
                        fallback = self._pick_fallback(
                            self._empty_fallbacks, "_last_empty_index"
                        )
                    logger.warning(
                        "[LLMEmptyGuard] LLM returned empty response (streak={}) — injecting: '{}'",
                        self._consecutive_empties,
                        fallback,
                    )
                    await self.push_frame(
                        TextFrame(text=fallback),
                        direction,
                    )
            elif not self._has_text and self._interrupted:
                logger.debug(
                    "[LLMEmptyGuard] Empty response after interruption — suppressed fallback"
                )
            # Reset for next response
            self._has_text = False
            self._interrupted = False
            self._timeout_fired = False
            self._is_background = False
            await self.push_frame(frame, direction)

        elif isinstance(frame, (InterruptionFrame, UserStartedSpeakingFrame)):
            self._cancel_timeout()
            was_streaming_llm_text = self._has_text
            self._has_text = False
            self._timeout_fired = False
            self._is_background = False
            if was_streaming_llm_text:
                self._interrupted = True
            await self.push_frame(frame, direction)

        else:
            await self.push_frame(frame, direction)