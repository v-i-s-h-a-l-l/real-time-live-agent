"""
naturalizer.py — ResponseNaturalizerProcessor
Voice-first text normalization + natural starter injection for Pipecat voice agents.

Design goals:
  - Make LLM output sound like a calm, natural human speaker
  - Inject contextually appropriate starters without repetition
  - Hard-reset cleanly on interruption — zero bleed between turns
  - Handle [BACKGROUND] sentinel from system prompt silently
  - Safe for multilingual text (English, Hindi, Hinglish, Devanagari)
  - Never mangle acronyms, IDs, short words, or legitimate punctuation
"""

import re
import random
import unicodedata
from collections import deque
from typing import Dict, List, Optional

from pipecat.frames.frames import (
    Frame,
    TextFrame,
    LLMFullResponseEndFrame,
    InterruptionFrame,
)
from pipecat.processors.frame_processor import (
    FrameDirection,
    FrameProcessor,
)


# ─────────────────────────────────────────────────────────────
# STARTERS
# Organised by conversational register.
# Empty string ("") is a valid starter — means "no prefix".
# Weight empties higher in neutral so silence is the default.
# ─────────────────────────────────────────────────────────────

STARTERS_EN: Dict[str, List[str]] = {
    "affirmative": ["Yeah, ", "Sure, ", "Right, ", "Got it — "],
    "explanatory": ["So, ", "Basically, ", "Well, ", "Actually, "],
    "insightful":  ["Ah, ", "Oh, ", "Interesting — ", "Right, "],
    "casual":      ["Okay, ", "Got it — ", "Hmm, ", "Sure — "],
    # empty entries give ~50 % silence rate on neutral responses
    "neutral":     ["", "", "", "Well, ", "So, "],
}

STARTERS_HI: Dict[str, List[str]] = {
    "affirmative": ["Haan, ", "Bilkul, ", "Sure, ", "Theek hai — "],
    "explanatory": ["Dekho, ", "Toh, ", "Actually, ", "Basically, "],
    "insightful":  ["Acha, ", "Oh, ", "Hmm — "],
    "casual":      ["Okay, ", "Acha, ", "Hmm, "],
    "neutral":     ["", "", "", "Toh, "],
}

# Semantic patterns → starter category
# Uses word-boundary anchors (\b) to avoid substring false positives.
# Ordered from most-specific to least-specific.
_SEMANTIC_RULES: List[tuple[str, str]] = [
    # affirmative signals
    (r"\b(yes|yeah|sure|correct|right|agree|exactly|indeed|of course|definitely)\b", "affirmative"),
    # insight / surprise signals
    (r"\b(interesting|surprising|actually|turns out|realize|notice|notably)\b", "insightful"),
    (r"^(oh|wow|ah)\b", "insightful"),
    # explanatory signals — only fire on whole-word "how", "why" etc.
    (r"\b(because|since|therefore|thus|for example|such as)\b", "explanatory"),
    (r"^(how|why|what|when)\b", "explanatory"),
]


# ─────────────────────────────────────────────────────────────
# TTS SYMBOL → SPOKEN FORM MAP
# Only symbols that a TTS engine might stumble on or read
# literally. Does NOT touch normal sentence punctuation.
# ─────────────────────────────────────────────────────────────

_SYMBOL_MAP: List[tuple[re.Pattern, str]] = [
    # ellipsis / multiple dots → natural pause comma
    (re.compile(r"\.{2,}"),           ", "),
    # markdown bold / italic / headers / hr
    (re.compile(r"\*{1,3}"),          ""),
    (re.compile(r"_{1,3}"),           ""),
    (re.compile(r"^#{1,6}\s*", re.M),""),
    (re.compile(r"^-{3,}$", re.M),   ""),
    # markdown list markers at line start (- item, * item, 1. item)
    (re.compile(r"^\s*[-*]\s+", re.M), ""),
    (re.compile(r"^\s*\d+\.\s+", re.M), ""),
    # inline code / code fences
    (re.compile(r"`{1,3}[^`]*`{1,3}"), ""),
    # URLs — drop entirely, agent says "I'll send that to you"
    (re.compile(r"https?://\S+"),     ""),
    # standalone pipe characters (table dividers)
    (re.compile(r"\s*\|\s*"),         " "),
    # double dash → em-dash pause (TTS reads this better)
    (re.compile(r"\s--\s"),           " — "),
    # multiple commas / spaces
    (re.compile(r",\s*,+"),           ", "),
    (re.compile(r" {2,}"),            " "),
]

# Robotic preamble phrases to strip from the START of a response.
# Applied before symbol cleaning so the text is fresh.
_ROBOTIC_PREAMBLES: List[re.Pattern] = [
    re.compile(r"^(As an AI[,.]?\s*)", re.I),
    re.compile(r"^(As a language model[,.]?\s*)", re.I),
    re.compile(r"^(Certainly!\s*(I'?d be happy to (help|assist)\.?\s*)?)", re.I),
    re.compile(r"^(Of course!\s*(I'?d be happy to (help|assist)\.?\s*)?)", re.I),
    re.compile(r"^(Absolutely!\s*(I'?d be happy to (help|assist)\.?\s*)?)", re.I),
    re.compile(r"^(Great question!\s*)", re.I),
    re.compile(r"^(Sure thing!\s*)", re.I),
]

# Mid-sentence robotic fragments to substitute.
_ROBOTIC_SUBS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"\bI don't have personal opinions\b", re.I), "from what I can tell"),
    (re.compile(r"\bI'm just an AI\b", re.I),                ""),
    (re.compile(r"\bI cannot provide\b", re.I),              "I can't share"),
    (re.compile(r"\bI am not able to\b", re.I),              "I can't"),
    (re.compile(r"\bAs per your request\b", re.I),           ""),
    (re.compile(r"\bPlease note that\b", re.I),              ""),
    (re.compile(r"\bIt's worth noting that\b", re.I),        ""),
    (re.compile(r"\bI hope this helps\b[.!]?", re.I),        ""),
    (re.compile(r"\bFeel free to\b", re.I),                  "go ahead and"),
]

# Sentinel emitted by the system prompt background-filter rule.
# Must be swallowed entirely — never sent to TTS.
_BACKGROUND_SENTINEL = "[BACKGROUND]"

# Minimum buffered characters before we attempt starter injection.
# Prevents picking a category from a single token like "Int" or "The".
_DEFAULT_MIN_CHUNK = 18

# How many words trigger "explanatory" vs "casual" on a neutral response.
_EXPLANATORY_WORD_THRESHOLD = 12


def _safe_lower_first(text: str) -> str:
    """
    Lowercase the first character of *text* safely for any Unicode script.
    Returns the original string unchanged if it is empty or starts with a
    non-letter (e.g., a digit or punctuation) — avoids crashing on
    Devanagari or other non-Latin scripts where case doesn't apply.
    """
    if not text:
        return text
    first = text[0]
    cat = unicodedata.category(first)
    # Only lowercase if it's an uppercase letter (Lu)
    if cat == "Lu":
        return first.lower() + text[1:]
    return text


class ResponseNaturalizerProcessor(FrameProcessor):
    """
    Pipecat FrameProcessor that:
      1. Strips robotic preambles and TTS-hostile symbols from LLM text output.
      2. Buffers streaming chunks until enough text is available to pick a
         semantically appropriate starter phrase.
      3. Injects that starter once (per response turn) at the front of the
         first flushed chunk.
      4. Hard-resets on InterruptionFrame — no partial text bleeds into the
         next turn.
      5. Silently drops [BACKGROUND] sentinel frames.
    """

    def __init__(
        self,
        *,
        language: str = "en-IN",
        add_starters: bool = True,
        min_chunk_length: int = _DEFAULT_MIN_CHUNK,
        starter_cooldown: int = 5,
        empty_starter_probability: float = 0.40,
        **kwargs,
    ):
        """
        Parameters
        ----------
        language : str
            BCP-47 language tag. "hi-IN" activates Hindi starters;
            everything else uses English starters.
        add_starters : bool
            Set False to disable starter injection entirely (useful in
            testing or when the TTS engine adds its own fillers).
        min_chunk_length : int
            Minimum buffered character count before starter injection fires.
            Lower = faster first audio, higher = more accurate category.
        starter_cooldown : int
            How many turns to remember previous starters to avoid repetition.
        empty_starter_probability : float
            Probability of choosing no starter on neutral responses.
            Range [0.0, 1.0]. Default 0.40 (40 % silence).
        """
        super().__init__(**kwargs)

        self._starters = STARTERS_HI if language == "hi-IN" else STARTERS_EN
        self._add_starters = add_starters
        self._min_chunk = min_chunk_length
        self._empty_p = empty_starter_probability
        self._recent: deque[str] = deque(maxlen=starter_cooldown)

        # Per-turn state
        self._buffer: str = ""
        self._starter_injected: bool = False

    # ── Semantic starter selection ───────────────────────────────────────────

    def _category_for(self, text: str) -> str:
        lower = text.lower()
        for pattern, category in _SEMANTIC_RULES:
            if re.search(pattern, lower):
                return category
        # Fallback: longer responses get explanatory, short get casual
        word_count = len(text.split())
        return "explanatory" if word_count >= _EXPLANATORY_WORD_THRESHOLD else "casual"

    def _pick_starter(self, text: str) -> str:
        if not self._add_starters:
            return ""

        category = self._category_for(text)

        # On neutral/casual categories, respect empty_starter_probability
        if category in ("neutral", "casual") and random.random() < self._empty_p:
            return ""

        pool = self._starters.get(category, self._starters["neutral"])

        # Exclude recently used non-empty starters to avoid repetition.
        # Empty string is always eligible (silence never gets "old").
        available = [s for s in pool if s == "" or s not in self._recent]
        if not available:
            available = pool  # full reset if all have been used

        starter = random.choice(available)
        if starter:
            self._recent.append(starter)
        return starter

    # ── Text cleaning ────────────────────────────────────────────────────────

    @staticmethod
    def _strip_preamble(text: str) -> str:
        for pattern in _ROBOTIC_PREAMBLES:
            text = pattern.sub("", text, count=1)
        return text.strip()

    @staticmethod
    def _apply_subs(text: str) -> str:
        for pattern, repl in _ROBOTIC_SUBS:
            text = pattern.sub(repl, text)
        return text

    @staticmethod
    def _apply_symbols(text: str) -> str:
        for pattern, repl in _SYMBOL_MAP:
            text = pattern.sub(repl, text)
        return text.strip()

    def _clean(self, text: str) -> str:
        """Full cleaning pipeline. Returns empty string if nothing survives."""
        if not text or not text.strip():
            return ""

        # 0. Swallow background sentinel silently
        if text.strip() == _BACKGROUND_SENTINEL:
            return ""

        text = text.strip()

        # 1. Strip robotic preambles from the front
        text = self._strip_preamble(text)
        if not text:
            return ""

        # 2. Mid-sentence robotic substitutions
        text = self._apply_subs(text)

        # 3. TTS symbol normalisation
        text = self._apply_symbols(text)

        # 4. Collapse any leftover whitespace
        text = re.sub(r" {2,}", " ", text).strip()

        # 5. Strip leading/trailing stray punctuation that reads badly aloud
        text = re.sub(r"^[,\-—;:]+\s*", "", text)
        text = re.sub(r"\s*[,;:]+$", "", text)

        return text

    # ── Turn state ───────────────────────────────────────────────────────────

    def _reset(self) -> None:
        """
        Hard reset between response turns.
        Discards any buffered text so interrupted responses never bleed.
        """
        self._buffer = ""
        self._starter_injected = False

    def _flush_buffer(self, direction: FrameDirection):
        """
        Coroutine-free helper that returns the final text to push (with
        starter prepended). Caller is responsible for pushing the frame.
        Resets buffer state after flushing.
        """
        buffered = self._buffer
        self._buffer = ""
        self._starter_injected = True   # mark done even if we reset after

        if not buffered:
            return None

        starter = self._pick_starter(buffered)
        if starter:
            # Lower-case the first character of the buffered text safely
            buffered = starter + _safe_lower_first(buffered)

        return buffered

    # ── Frame processing ─────────────────────────────────────────────────────

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # ── TextFrame: main path ─────────────────────────────────────────────
        if isinstance(frame, TextFrame):
            text = self._clean(frame.text)

            if not text:
                # Cleaned to nothing — pass original through so TTS/downstream
                # processors don't stall on a missing frame.
                await self.push_frame(frame, direction)
                return

            if not self._starter_injected:
                # Accumulate into buffer
                self._buffer = (self._buffer + " " + text).strip() if self._buffer else text

                if len(self._buffer) >= self._min_chunk:
                    # Buffer is large enough — inject starter and flush
                    final = self._flush_buffer(direction)
                    if final:
                        await self.push_frame(TextFrame(text=final), direction)
                # else: still buffering — hold, don't push yet

            else:
                # Starter already injected — stream chunks straight through
                await self.push_frame(TextFrame(text=text), direction)

        # ── End of LLM response ──────────────────────────────────────────────
        elif isinstance(frame, LLMFullResponseEndFrame):
            # Edge case: entire response was shorter than min_chunk_length.
            # Flush whatever's left in the buffer before resetting.
            if self._buffer:
                final = self._flush_buffer(direction)
                if final:
                    await self.push_frame(TextFrame(text=final), direction)

            self._reset()
            await self.push_frame(frame, direction)

        # ── Interruption ─────────────────────────────────────────────────────
        elif isinstance(frame, InterruptionFrame):
            # Hard reset — discard buffer entirely.
            # Partial interrupted text must NEVER reach TTS.
            self._reset()
            await self.push_frame(frame, direction)

        # ── All other frames pass through unchanged ───────────────────────────
        else:
            await self.push_frame(frame, direction)