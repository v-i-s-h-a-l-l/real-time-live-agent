"""Resume an interrupted tutor turn after incidental noise (cough, etc.).

Barge-in still stops TTS immediately. After the user turn ends, a heuristic
(no extra LLM call) decides:

- incidental sound / empty STT → speak the unfinished remainder
- meaningful speech ("Wait, why…", "No.") → normal interruption

Place ``IncidentalResumeGateProcessor`` before the user aggregator (so
incidental transcripts never become a user turn) and
``IncidentalResumeCaptureProcessor`` after the naturalizer (so remainder is
the text actually sent to TTS).
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseStartFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Spoken English is ~150–160 wpm ≈ 13 chars/s. Slightly low so resume overlaps
# a word or two rather than skipping ahead.
_CHARS_PER_SEC = 13.0
_MIN_REMAINDER_CHARS = 12
# Wait for a late STT result after the user turn ends. Does not delay barge-in
# or a meaningful transcript (those abort resume immediately).
_STT_GRACE_SECS = 1.2
# Longer than a cough/sneeze; a real utterance STT missed should not auto-resume.
_MAX_INCIDENTAL_SECS = 1.5

_FILLERS = frozenset(
    {
        "uh",
        "um",
        "umm",
        "uhh",
        "er",
        "eh",
        "ah",
        "ahh",
        "hmm",
        "hm",
        "mm",
        "mmm",
        "mhm",
        "tsk",
        "pff",
        "pfft",
        "tch",
        "huhuh",
        "ahem",
        "cough",
        "coughs",
        "coughing",
        "sneeze",
        "sneezes",
        "sneezing",
        "throat",
        "clearing",
        "sniff",
        "sniffle",
        "sigh",
        "noise",
        "background",
    }
)

# Short but intentional — never treat these as coughs.
_MEANINGFUL_SHORT = frozenset(
    {
        "why",
        "how",
        "wait",
        "no",
        "what",
        "yes",
        "yeah",
        "yep",
        "nah",
        "ok",
        "okay",
        "huh",
        "stop",
        "hold",
        "hint",
        "again",
        "continue",
        "go",
        "sorry",
        "don't",
        "dont",
        "not",
        "explain",
        "slow",
        "repeat",
        "help",
        "skip",
        "next",
        "back",
        "break",
        "pause",
        "who",
        "when",
        "where",
        "which",
        "whose",
        "because",
        "and",
        "but",
        "so",
        "if",
        "true",
        "false",
        "right",
        "wrong",
        "more",
        "less",
        "see",
        "look",
        "show",
        "tell",
        "please",
    }
)

_SOUND_MARKERS = re.compile(
    r"[\(\[]\s*(cough|sneeze|ahem|throat|sniff|sigh|noise)s?\s*[\)\]]|"
    r"\*(cough|sneeze|ahem|throat|sniff|sigh)s?\*",
    re.I,
)
_NON_WORD = re.compile(r"[^A-Za-z0-9']+")
_WORD = re.compile(r"[A-Za-z0-9']+")


def is_incidental_utterance(text: str | None) -> bool:
    """True when STT has no meaningful user intent (cough, filler, empty)."""
    raw = (text or "").strip()
    if not raw:
        return True
    if _SOUND_MARKERS.search(raw):
        stripped = _SOUND_MARKERS.sub(" ", raw)
        if not stripped.strip():
            return True
        raw = stripped
    words = [w.lower() for w in _WORD.findall(raw)]
    if not words:
        return True
    if any(w in _MEANINGFUL_SHORT for w in words):
        return False
    if all(w in _FILLERS for w in words):
        return True
    # Single unknown token: letters/digits are likely math or a real word.
    if len(words) == 1:
        token = words[0]
        if token in _FILLERS:
            return True
        if len(token) <= 2 and not token.isalnum():
            return True
        return False
    return False


def remainder_after_cut(text: str, chars_spoken: int) -> str:
    """Keep the unspoken tail, snapping back to a nearby word/sentence boundary."""
    text = (text or "").strip()
    if not text:
        return ""
    if chars_spoken <= 0:
        return text
    if chars_spoken >= len(text):
        return ""
    tail_direct = text[chars_spoken:].lstrip()
    if len(tail_direct) < _MIN_REMAINDER_CHARS:
        return ""
    cut = chars_spoken
    window_start = max(0, cut - 48)
    region = text[window_start:cut]
    snapped = None
    for sep in (". ", "? ", "! ", ", ", "; ", ": ", " "):
        idx = region.rfind(sep)
        if idx != -1:
            snapped = window_start + idx + len(sep)
            break
    if snapped is None:
        snapped = cut
    remainder = text[snapped:].lstrip()
    return remainder if len(remainder) >= _MIN_REMAINDER_CHARS else ""


class IncidentalResumeStore:
    """Continuation state for one interrupted assistant turn."""

    def __init__(self) -> None:
        self.generation = 0
        self._spoken = ""
        self._unflushed = ""
        self._remainder = ""
        self._full = ""
        self._bot_started_at: float | None = None
        self._user_started_at: float | None = None
        self._pending = False
        self._speaking_turn = False

    @property
    def pending(self) -> bool:
        return self._pending

    @property
    def remainder(self) -> str:
        return self._remainder

    @property
    def full_text(self) -> str:
        return self._full

    def begin_turn(self) -> None:
        """A new LLM reply started — cancel any pending cough-resume."""
        self.generation += 1
        self._spoken = ""
        self._unflushed = ""
        self._remainder = ""
        self._full = ""
        self._bot_started_at = None
        self._pending = False
        self._speaking_turn = True

    def append_spoken(self, text: str) -> None:
        if not text or not self._speaking_turn:
            return
        self._spoken += text

    def stash_unflushed(self, text: str) -> None:
        """Naturalizer hold that never reached TTS before the interrupt."""
        if not text:
            return
        self._unflushed += text
        if self._pending:
            self._recompute()

    def on_bot_started(self) -> None:
        if self._bot_started_at is None:
            self._bot_started_at = time.monotonic()

    def on_user_started(self) -> None:
        self._user_started_at = time.monotonic()

    def user_turn_secs(self) -> float:
        if self._user_started_at is None:
            return 0.0
        return max(0.0, time.monotonic() - self._user_started_at)

    def on_interrupted(self) -> None:
        if not self._speaking_turn:
            return
        self._speaking_turn = False
        assembled = (self._spoken + " " + self._unflushed).strip()
        if len(assembled) < _MIN_REMAINDER_CHARS:
            self._pending = False
            self._remainder = ""
            self._full = assembled
            return
        self._pending = True
        self._recompute()
        logger.info(
            "[IncidentalResume] interrupted — kept {} chars, remainder {} chars",
            len(self._full),
            len(self._remainder),
        )

    def abort(self) -> None:
        """Meaningful user speech — keep normal barge-in, do not resume."""
        self.generation += 1
        self._pending = False
        self._remainder = ""
        self._speaking_turn = False
        self._user_started_at = None

    def consume_resume(self) -> str | None:
        if not self._pending:
            return None
        remainder = self._remainder.strip()
        full = self._full
        self.generation += 1
        self._pending = False
        self._unflushed = ""
        self._remainder = ""
        self._user_started_at = None
        if len(remainder) < _MIN_REMAINDER_CHARS:
            self._speaking_turn = False
            return None
        # Remainder is now the in-flight tutor turn, so a second cough can resume again.
        self._spoken = remainder
        self._full = full
        self._bot_started_at = None
        self._speaking_turn = True
        return remainder

    def should_resume(self, utterance: str | None, *, user_secs: float) -> bool:
        if not self._pending or not self._remainder:
            return False
        if user_secs >= _MAX_INCIDENTAL_SECS and not (utterance or "").strip():
            # Long empty turn: more likely missed speech than a cough.
            return False
        return is_incidental_utterance(utterance)

    def _recompute(self) -> None:
        full = (self._spoken + " " + self._unflushed).strip()
        self._full = full
        elapsed = 0.0
        if self._bot_started_at is not None:
            elapsed = max(0.0, time.monotonic() - self._bot_started_at)
        chars_spoken = int(elapsed * _CHARS_PER_SEC)
        self._remainder = remainder_after_cut(full, chars_spoken)


def restore_assistant_text(context: LLMContext, full_text: str) -> None:
    """Keep the unfinished explanation in context instead of a cut-off stub."""
    if not full_text.strip():
        return
    messages = context.messages
    if messages and messages[-1].get("role") == "assistant":
        messages[-1] = dict(messages[-1])
        messages[-1]["content"] = full_text
        return
    context.add_message({"role": "assistant", "content": full_text})


class IncidentalResumeGateProcessor(FrameProcessor):
    """Drop incidental transcripts after barge-in and resume the leftover TTS."""

    def __init__(
        self,
        store: IncidentalResumeStore,
        context: LLMContext,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._store = store
        self._context = context
        self._resume_task: asyncio.Task | None = None
        self._user_stopped = False
        self._incidental_seen = False

    def _cancel_timer(self) -> None:
        task = self._resume_task
        self._resume_task = None
        if task is not None and not task.done():
            task.cancel()

    def _arm_timer(self) -> None:
        self._cancel_timer()
        generation = self._store.generation
        self._resume_task = asyncio.create_task(self._delayed_resume(generation))

    async def _delayed_resume(self, generation: int) -> None:
        try:
            await asyncio.sleep(_STT_GRACE_SECS)
        except asyncio.CancelledError:
            return
        if generation != self._store.generation:
            return
        user_secs = self._store.user_turn_secs()
        if not self._store.should_resume("", user_secs=user_secs):
            if self._store.pending:
                logger.info(
                    "[IncidentalResume] empty STT after {:.1f}s — not treating as cough",
                    user_secs,
                )
                self._store.abort()
            return
        await self._resume("empty STT")

    async def _resume(self, reason: str) -> None:
        remainder = self._store.consume_resume()
        if not remainder:
            return
        restore_assistant_text(self._context, self._store.full_text)
        logger.info(
            "[IncidentalResume] {} — resuming {} chars",
            reason,
            len(remainder),
        )
        await self.push_frame(
            TTSSpeakFrame(text=remainder, append_to_context=False),
            FrameDirection.DOWNSTREAM,
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InterruptionFrame):
            self._store.on_interrupted()
            self._cancel_timer()
            self._user_stopped = False
            self._incidental_seen = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStartedSpeakingFrame):
            self._store.on_user_started()
            self._user_stopped = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStoppedSpeakingFrame):
            self._user_stopped = True
            await self.push_frame(frame, direction)
            if self._store.pending and self._incidental_seen:
                self._cancel_timer()
                await self._resume("incidental after user stop")
            elif self._store.pending:
                self._arm_timer()
            return

        if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
            text = frame.text or ""
            if self._store.pending:
                user_secs = self._store.user_turn_secs()
                if self._store.should_resume(text, user_secs=user_secs):
                    self._incidental_seen = True
                    self._cancel_timer()
                    logger.info(
                        "[IncidentalResume] incidental transcript={!r} — suppressing user turn",
                        text[:80],
                    )
                    # Browser barge-in often never starts a server user-turn, so
                    # UserStoppedSpeakingFrame never arrives. Resume as soon as
                    # STT shows there was no real intent.
                    await self._resume(f"incidental {text[:40]!r}")
                    return
                logger.info(
                    "[IncidentalResume] meaningful interruption={!r}",
                    text[:80],
                )
                self._store.abort()
                self._cancel_timer()
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)


class IncidentalResumeCaptureProcessor(FrameProcessor):
    """Record spoken TTS text so an incidental barge-in can continue it."""

    def __init__(self, store: IncidentalResumeStore, **kwargs: Any):
        super().__init__(**kwargs)
        self._store = store

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._store.begin_turn()
        elif isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
            self._store.append_spoken(frame.text)
        elif isinstance(frame, BotStartedSpeakingFrame):
            self._store.on_bot_started()
        elif isinstance(frame, InterruptionFrame):
            self._store.on_interrupted()

        await self.push_frame(frame, direction)
