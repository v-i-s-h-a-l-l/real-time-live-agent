import re
from typing import Optional
from loguru import logger

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMMessagesAppendFrame,
    InterruptionFrame,
    TextFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


# ─── Pivot signal words / phrases ────────────────────────────────────────────
# English + Hindi + Hinglish — all lowercased, word-boundary anchored.
# These are *strong* pivot signals: topic abandonment, redirect, interruption.
PIVOT_PATTERNS: list[str] = [
    # English
    r"\bactually\b",
    r"\bwait\b",
    r"\bnever mind\b",
    r"\bforget (that|it)\b",
    r"\bby the way\b",
    r"\boh wait\b",
    r"\bsomething else\b",
    r"\bswitching gears\b",
    r"\blet me ask you\b",
    r"\bquick question\b",
    r"\bone more thing\b",
    r"\bscrap that\b",
    r"\bhold on\b",
    r"\bstop stop\b",
    r"\bwait wait\b",
    r"\bignore that\b",
    r"\bchange of topic\b",
    r"\bdifferent question\b",
    # Hindi
    r"\bruko\b",
    r"\bek second\b",
    r"\balag baat\b",
    r"\bwaise\b",
    r"\bacha suno\b",
    r"\bbas bas\b",
    r"\bchhodo\b",          # "forget it"
    r"\bchhod yeh\b",
    r"\balag topic\b",
    r"\bdusri baat\b",      # "different thing"
    r"\bek minute\b",
    r"\byaar sun\b",
    r"\bbhai sun\b",
    r"\bsuno suno\b",
    r"\balag sawaal\b",     # "different question"
    r"\bmaafi\b",           # "sorry" — often precedes redirect
    r"\bnahi nahi\b",       # "no no" — self-correction signal
    r"\btheek hai suno\b",  # "okay listen"
    # Hinglish combos
    r"\bactually yaar\b",
    r"\bwait yaar\b",
    r"\bhold on yaar\b",
    r"\bek sec\b",
    r"\bone sec\b",
]

# Pre-compiled for speed — compiled once at import time
_PIVOT_RE = re.compile(
    "|".join(PIVOT_PATTERNS),
    re.IGNORECASE | re.UNICODE,
)

# Stop words for semantic overlap calculation (English + Hindi)
_STOP_WORDS: frozenset[str] = frozenset({
    # English
    "the", "a", "an", "is", "are", "was", "were", "i", "you", "we", "it",
    "of", "to", "in", "and", "or", "that", "this", "me", "my", "your",
    "do", "did", "can", "please", "just", "like", "so", "what", "how",
    "get", "got", "yeah", "yes", "no", "ok", "okay", "right", "well",
    # Hindi common fillers
    "hai", "hain", "ho", "tha", "thi", "the", "aur", "ya", "ki",
    "ke", "ka", "ko", "se", "mein", "ne", "bhi", "toh", "na",
    "kya", "kaise", "kab", "kyun", "jo", "ab", "yeh", "woh",
})

# Semantic overlap threshold — CONSERVATIVE on purpose.
# Low threshold = too many false pivots (normal follow-ups flagged).
# 0.08 means: fire only when < 8% of meaningful words overlap.
_SEMANTIC_PIVOT_THRESHOLD: float = 0.08

# How many complete bot utterances to remember for semantic comparison.
# We use the *last full response*, not streaming tokens.
_BOT_MEMORY_UTTERANCES: int = 1


class PivotDetectorProcessor(FrameProcessor):
    """
    Detects mid-conversation topic pivots and handles them gracefully.

    Detection methods (both must agree, or pattern alone suffices):
      1. Pattern pivot  — regex match on strong redirect phrases (English/Hindi/Hinglish)
      2. Semantic pivot — Jaccard similarity of content words falls below threshold
                          AND current utterance is a full sentence (not a short fragment)

    On pivot:
      • Fires InterruptionFrame DOWNSTREAM to stop bot audio immediately
      • Injects a one-time system hint into LLMMessagesAppendFrame so the LLM
        acknowledges the shift naturally and answers the new topic

    Args:
        semantic_pivot: enable/disable semantic pivot detection (default True)
        min_semantic_words: minimum meaningful words required to attempt semantic
                            comparison — prevents very short inputs from triggering (default 4)
        pivot_hint_lang: "en" | "hi" | "auto"
                         "auto" inspects the transcript for Devanagari to pick language
    """

    def __init__(
        self,
        *,
        semantic_pivot: bool = True,
        min_semantic_words: int = 4,
        pivot_hint_lang: str = "auto",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._semantic_pivot_enabled = semantic_pivot
        self._min_semantic_words = min_semantic_words
        self._pivot_hint_lang = pivot_hint_lang

        # State — reset per user utterance
        self._pivot_flagged: bool = False
        self._pivot_text: Optional[str] = None
        self._pivot_hint_injected: bool = False  # gate: inject only once per utterance

        # Accumulates bot response tokens into a full utterance
        self._bot_buffer: list[str] = []
        self._last_bot_utterance: str = ""
        self._bot_interrupted: bool = False  # True if bot was cut off mid-response

    # ── Frame routing ────────────────────────────────────────────────────────

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, UserStartedSpeakingFrame):
            await self._reset_utterance_state()
            await self.push_frame(frame, direction)

        elif isinstance(frame, UserStoppedSpeakingFrame):
            # Only commit if the bot wasn't interrupted mid-response.
            # If interrupted, the buffer holds a partial utterance — stale
            # context is worse than no context, so we discard it and keep
            # whatever the last *complete* utterance was.
            if not self._bot_interrupted:
                committed = " ".join(self._bot_buffer).strip()
                if committed:
                    self._last_bot_utterance = committed
            self._bot_buffer.clear()
            self._bot_interrupted = False
            await self.push_frame(frame, direction)

        elif isinstance(frame, LLMFullResponseEndFrame):
            # Bot finished a complete response — safe to commit the buffer now
            # (belt-and-suspenders alongside UserStoppedSpeakingFrame)
            if not self._bot_interrupted:
                committed = " ".join(self._bot_buffer).strip()
                if committed:
                    self._last_bot_utterance = committed
            await self.push_frame(frame, direction)

        elif isinstance(frame, InterruptionFrame):
            # Bot was cut off — mark buffer as dirty so UserStoppedSpeakingFrame
            # doesn't commit the partial response as authoritative context
            self._bot_interrupted = True
            self._bot_buffer.clear()
            logger.debug("[PivotDetector] Bot interrupted — bot buffer discarded")
            await self.push_frame(frame, direction)

        elif isinstance(frame, TranscriptionFrame):
            await self._handle_transcription(frame, direction)

        elif isinstance(frame, LLMMessagesAppendFrame):
            await self._handle_llm_messages(frame, direction)

        elif isinstance(frame, TextFrame):
            # Accumulate streaming bot tokens — we commit on UserStoppedSpeakingFrame
            if frame.text:
                self._bot_buffer.append(frame.text)
            await self.push_frame(frame, direction)

        else:
            await self.push_frame(frame, direction)

    # ── Transcription handler ────────────────────────────────────────────────

    async def _handle_transcription(
        self, frame: TranscriptionFrame, direction: FrameDirection
    ):
        text = frame.text.strip()
        if not text:
            await self.push_frame(frame, direction)
            return

        is_pattern = self._pattern_pivot(text)
        is_semantic = (
            self._semantic_pivot_enabled
            and self._semantic_pivot(text)
        )

        if is_pattern or is_semantic:
            self._pivot_flagged = True
            self._pivot_text = text
            method = "pattern" if is_pattern else "semantic"
            logger.info(
                f"[PivotDetector] Pivot detected ({method}): '{text[:80]}'"
            )
            # Stop bot audio — DOWNSTREAM so it reaches TTS/audio sink
            await self.push_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)

        await self.push_frame(frame, direction)

    # ── LLM messages handler ─────────────────────────────────────────────────

    async def _handle_llm_messages(
        self, frame: LLMMessagesAppendFrame, direction: FrameDirection
    ):
        if (
            self._pivot_flagged
            and self._pivot_text
            and not self._pivot_hint_injected
        ):
            hint = self._build_pivot_hint(self._pivot_text)
            messages = list(frame.messages)
            # Insert just before the final user message so the LLM sees:
            # [...history, PIVOT_HINT, user_new_message]
            messages.insert(-1, hint)
            frame = LLMMessagesAppendFrame(messages=messages)
            self._pivot_hint_injected = True  # prevent double injection
            logger.debug(f"[PivotDetector] Injected pivot hint for: '{self._pivot_text[:60]}'")

        await self.push_frame(frame, direction)

    # ── Pivot detection logic ────────────────────────────────────────────────

    def _pattern_pivot(self, text: str) -> bool:
        """True if any strong redirect phrase is found in the text."""
        return bool(_PIVOT_RE.search(text))

    def _semantic_pivot(self, new_text: str) -> bool:
        """
        True if the user's new input shares almost no content words with the
        last bot utterance — AND the new input has enough content to compare.

        Uses Jaccard similarity on stemmed content words (stopwords removed).
        Conservative threshold: only fires on near-zero overlap.
        """
        if not self._last_bot_utterance:
            return False

        bot_words = self._content_words(self._last_bot_utterance)
        new_words = self._content_words(new_text)

        # Don't fire on very short inputs — fragments like "haan", "okay",
        # "theek hai" are not pivots, they're acknowledgements.
        if len(new_words) < self._min_semantic_words:
            return False

        if not bot_words:
            return False

        intersection = len(bot_words & new_words)
        union = len(bot_words | new_words)
        if union == 0:
            return False

        jaccard = intersection / union
        is_pivot = jaccard < _SEMANTIC_PIVOT_THRESHOLD

        if is_pivot:
            logger.debug(
                f"[PivotDetector] Semantic pivot: jaccard={jaccard:.2f} "
                f"(bot_words={len(bot_words)}, new_words={len(new_words)})"
            )
        return is_pivot

    def _content_words(self, text: str) -> set[str]:
        """Lowercased words with stopwords and punctuation removed."""
        return {
            w.lower().strip(".,!?\"'।—-")
            for w in text.split()
            if w.lower().strip(".,!?\"'।—-") not in _STOP_WORDS
            and len(w) > 1
        }

    # ── Pivot hint construction ───────────────────────────────────────────────

    def _build_pivot_hint(self, pivot_text: str) -> dict:
        """
        Constructs the system hint message injected into the LLM context.
        Language is auto-detected or set via pivot_hint_lang constructor arg.
        """
        lang = self._pivot_hint_lang
        if lang == "auto":
            # Detect Devanagari characters in the pivot text
            lang = "hi" if re.search(r"[\u0900-\u097F]", pivot_text) else "en"

        if lang == "hi":
            content = (
                f"User ne topic change kiya hai. Unka naya message hai: "
                f"{repr(pivot_text)}. "
                f"Ek short phrase mein smoothly acknowledge karo ki conversation "
                f"shift ho gayi, phir seedha naye topic ka jawab do. "
                f"Bahut chhota response rakho."
            )
        else:
            content = (
                f"The user just changed the topic. Their new message is: "
                f"{repr(pivot_text)}. "
                f"In one short phrase, smoothly acknowledge the shift, "
                f"then answer the new topic directly. Keep your response brief."
            )

        return {"role": "system", "content": content}

    # ── State management ─────────────────────────────────────────────────────

    async def _reset_utterance_state(self):
        """Reset per-utterance state when the user starts speaking again."""
        self._pivot_flagged = False
        self._pivot_text = None
        self._pivot_hint_injected = False
        self._bot_interrupted = False