"""
RepeatDetectorProcessor
───────────────────────
Detects when the user asks the bot to repeat its last response.

When repeat intent is detected:
1. Looks up the last assistant message in the LLM context
2. Injects a system hint carrying the exact last response
3. LLM repeats it naturally instead of regenerating from scratch

Place this AFTER stt and call_mute, BEFORE user_aggregator in the pipeline.
"""
import re
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    LLMMessagesAppendFrame,
    TranscriptionFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
REPEAT_PATTERNS = [
    r"\b(say|repeat|tell me)\s+(that|it|this)\s+again\b",
    r"\bcan\s+you\s+repeat\b",
    r"\brepeat\s+that\b",
    r"\bsay\s+that\s+again\b",
    r"\bwhat\s+did\s+you\s+say\b",
    r"\bonce\s+more\b",
    r"\bone\s+more\s+time\b",
    r"\bdidn'?t\s+(catch|hear)\s+that\b",
    r"\bcouldn'?t\s+hear\b",
    r"\bcouldn'?t\s+catch\b",
    r"\bdidn'?t\s+get\s+that\b",
    r"\bpardon\b",
    r"\bcome\s+again\b",
    r"\bwhat\s+was\s+that\b",
    r"\bhuh\?\s*$",
    r"\bcan\s+you\s+say\s+that\s+again\b",
    r"\brepeat\s+it\b",
    r"\bsay\s+it\s+again\b",
    r"\b(please\s+)?repeat\b",
]

_REPEAT_RE = [re.compile(p, re.IGNORECASE) for p in REPEAT_PATTERNS]


def _is_repeat_intent(text: str) -> bool:
    return any(p.search(text) for p in _REPEAT_RE)


def _get_last_assistant_message(context: LLMContext) -> str | None:
    """Walk context messages in reverse and return the last assistant content."""
    for msg in reversed(context.messages):
        if msg.get("role") == "assistant":
            content = (msg.get("content") or "").strip()
            if content:
                return content
    return None


class RepeatDetectorProcessor(FrameProcessor):
    """
    Intercepts TranscriptionFrames with repeat intent.
    Injects a [USER_WANTS_REPEAT] system hint into the LLMMessagesAppendFrame
    so the LLM knows exactly what to repeat — no regeneration guesswork.
    """

    def __init__(self, context: LLMContext, **kwargs):
        super().__init__(**kwargs)
        self._context = context
        self._repeat_pending = False
        self._last_assistant_msg: str | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # ── Transcription — check for repeat intent ──────────────────────
        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()

            if text and _is_repeat_intent(text):
                last = _get_last_assistant_message(self._context)

                if last:
                    self._repeat_pending = True
                    self._last_assistant_msg = last
                    logger.info(
                        "[RepeatDetector] Repeat intent detected | last_msg='{}'",
                        last[:80],
                    )
                else:
                    # Nothing to repeat yet — let it through normally
                    logger.info(
                        "[RepeatDetector] Repeat intent but no prior assistant message — passing through"
                    )

            await self.push_frame(frame, direction)
            return

        # ── LLMMessagesAppendFrame — inject hint if repeat pending ────────
        if isinstance(frame, LLMMessagesAppendFrame):
            if self._repeat_pending and self._last_assistant_msg:
                self._repeat_pending = False  # consume the flag

                hint = {
                    "role": "system",
                    "content": (
                        f"[USER_WANTS_REPEAT] The user is asking you to repeat your last response. "
                        f"Your last response was: \"{self._last_assistant_msg}\" "
                        f"Repeat it naturally — same meaning, similar wording. "
                        f"Do NOT add new information. Do NOT say 'as I said' or 'like I mentioned'. "
                        f"Just say it again as if you're saying it for the first time, naturally."
                    ),
                }

                messages = list(frame.messages)
                # Insert hint just before the last message (user's utterance)
                if len(messages) > 0:
                    messages.insert(-1, hint)
                else:
                    messages.append(hint)

                frame = LLMMessagesAppendFrame(messages=messages)

                logger.info(
                    "[RepeatDetector] Injected repeat hint | msg='{}'",
                    self._last_assistant_msg[:80],
                )

            await self.push_frame(frame, direction)
            return

        # ── Everything else passes through ───────────────────────────────
        await self.push_frame(frame, direction)