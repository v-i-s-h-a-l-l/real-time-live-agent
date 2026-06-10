"""
IntentClassifierProcessor
─────────────────────────
Classifies transcribed text into one of three categories:

    DIRECTED_TO_ASSISTANT  — User is talking to Louie
    BACKGROUND_CONVERSATION — User is talking to someone else
    UNCERTAIN              — Ambiguous; defaults to silence

Three-tier classification:
    1. Wake word detection       → instant DIRECTED_TO_ASSISTANT
    2. Pattern-based heuristics  → fast classification (~0ms)
    3. LLM fallback              → slow path for UNCERTAIN (~100–200ms)

Place this AFTER the STT in the pipeline so it receives TranscriptionFrames.
"""

import re
import enum
from typing import Optional

from loguru import logger

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    LLMMessagesAppendFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class Intent(enum.Enum):
    DIRECTED_TO_ASSISTANT = "DIRECTED_TO_ASSISTANT"
    BACKGROUND_CONVERSATION = "BACKGROUND_CONVERSATION"
    UNCERTAIN = "UNCERTAIN"


# ── Wake words ───────────────────────────────────────────────────────────────
WAKE_PATTERNS = [
    r"\b(?:hey\s+)?louie\b",
    r"\b(?:hi\s+)?louie\b",
    r"\b(?:ok(?:ay)?\s+)?louie\b",
    r"\blouie[\s,!.?]",
]
_WAKE_RE = re.compile("|".join(WAKE_PATTERNS), re.IGNORECASE)

# ── Directed-to-assistant patterns ───────────────────────────────────────────
# Imperative commands + assistant-relevant topics
DIRECTED_PATTERNS = [
    # Direct commands
    r"^\s*(?:play|pause|stop|skip|next|previous|resume)\b",
    r"^\s*(?:set|create|add|remove|delete|cancel)\b",
    r"^\s*(?:show|tell|find|search|look up|google)\b",
    r"^\s*(?:remind|schedule|alarm|timer)\b",
    r"^\s*(?:call|text|message|send|email)\b",
    r"^\s*(?:open|close|launch|start|run)\b",
    r"^\s*(?:turn (?:on|off|up|down))\b",
    r"^\s*(?:increase|decrease|lower|raise)\s+(?:the\s+)?(?:volume|brightness|temperature)\b",
    # Questions directed at an assistant
    r"(?:what(?:'s| is| are)|how (?:do|does|can|is|are|much|many|long)|when (?:is|does|will|did)|where (?:is|are|can)|who (?:is|are|was)|why (?:is|does|did|can))\b",
    # Weather, time, calculations
    r"\b(?:weather|temperature|forecast|time|date|calculate|convert)\b",
    # Self-referencing to the assistant
    r"\b(?:can you|could you|would you|please|help me|i need you to|i need help|need help|help with)\b",
    # Check/status queries
    r"\b(?:check my|what's my|show my|my balance|my account|my schedule)\b",
    # Account / service keywords (strong signal when speaker-verified)
    r"\b(?:account|balance|payment|transaction|password|billing|subscription|order|refund|invoice)\b",
    r"\b(?:details|information|status|update|reset|change|modify)\b",
    # Short affirmations mid-conversation (continuing an existing dialog)
    r"^\s*(?:yes|yeah|yep|no|nope|okay|ok|sure|exactly|correct|right|thanks|thank you|bye|goodbye)\s*[.!?]?\s*$",
]
_DIRECTED_RE = re.compile("|".join(DIRECTED_PATTERNS), re.IGNORECASE)

# ── Background conversation patterns ─────────────────────────────────────────
# Social/conversational phrases addressed to humans
BACKGROUND_PATTERNS = [
    # Addressing specific people
    r"\b(?:bro|dude|man|bhai|yaar|boss)\b",
    r"\b(?:mom|dad|papa|mummy|amma|appa|ma|baba)\b",
    r"\b(?:sir|ma'am|madam)\b",
    # Social/human conversation
    r"\b(?:did you eat|have you eaten|let's go|come here|go there)\b",
    r"\b(?:i'll be home|i'm coming|i'm leaving|i'm going|i'm here)\b",
    r"\b(?:pass me|give me the|hand me)\b",
    r"\b(?:what are you doing|where are you going|kya kar raha|kahan ja raha)\b",
    r"\b(?:bye|see you|take care|good night|good morning)\s+(?:bro|dude|man|bhai|yaar|mom|dad|sir)\b",
    # Hindi/Hinglish social phrases
    r"\b(?:khana kha liya|chal|chalo|ruko|sun|suno|bol na|bata na)\b",
    r"\b(?:acha theek hai|haan bhai|nahi yaar)\b",
    r"\b(?:kya hua|kaise ho|kidhar hai|kab aayega)\b",
]
_BACKGROUND_RE = re.compile("|".join(BACKGROUND_PATTERNS), re.IGNORECASE)

# ── LLM classification prompt ────────────────────────────────────────────────
_CLASSIFY_PROMPT = """You are a classifier. Classify the following utterance as exactly one of: ASSISTANT, BACKGROUND.

Context: The user is near a voice assistant called Louie. Determine if the utterance is directed at the voice assistant (a command, question, or request) or is part of a background conversation with another person.

Rules:
- If it sounds like a command, question, or request for information → ASSISTANT
- If it sounds like casual human-to-human conversation → BACKGROUND
- When in doubt, lean toward BACKGROUND

Utterance: "{text}"

Classification (respond with exactly one word — ASSISTANT or BACKGROUND):"""


class IntentClassifierProcessor(FrameProcessor):
    """
    Classify transcriptions to determine if the user is talking to Louie.

    Args:
        llm_service:       The LLM service instance (e.g., CerebrasLLMService)
                           Used only for the UNCERTAIN → LLM fallback path.
        uncertain_default:  What to do when classification is UNCERTAIN and
                           LLM fallback is disabled or inconclusive.
                           "silence" (default) or "respond".
        use_llm_fallback:  Whether to use LLM for UNCERTAIN cases.
                           Set to False to skip LLM entirely (faster but less accurate).
    """

    def __init__(
        self,
        llm_service=None,
        uncertain_default: str = "silence",
        use_llm_fallback: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._llm_service = llm_service
        self._uncertain_default = uncertain_default
        self._use_llm_fallback = use_llm_fallback

        # Per-turn state
        self._turn_suppressed = False
        self._current_transcription: Optional[str] = None

        # Stats
        self._total_classified = 0
        self._directed_count = 0
        self._background_count = 0
        self._uncertain_count = 0

        logger.info(
            "[IntentClassifier] Initialized | uncertain_default={} llm_fallback={}",
            uncertain_default,
            use_llm_fallback,
        )

    def _classify_fast(self, text: str) -> Intent:
        """
        Fast pattern-based classification (Tier 1 + Tier 2).
        Returns UNCERTAIN if no pattern matches confidently.
        """
        text_stripped = text.strip()
        if not text_stripped:
            return Intent.UNCERTAIN

        # Tier 1: Wake word — always DIRECTED
        if _WAKE_RE.search(text_stripped):
            logger.debug("[IntentClassifier] Wake word detected: '{}'", text_stripped[:60])
            return Intent.DIRECTED_TO_ASSISTANT

        # Tier 2a: Background conversation patterns
        if _BACKGROUND_RE.search(text_stripped):
            # Double-check: if it also matches directed patterns, it's UNCERTAIN
            if _DIRECTED_RE.search(text_stripped):
                return Intent.UNCERTAIN
            return Intent.BACKGROUND_CONVERSATION

        # Tier 2b: Directed-to-assistant patterns
        if _DIRECTED_RE.search(text_stripped):
            return Intent.DIRECTED_TO_ASSISTANT

        # No strong match either way
        return Intent.UNCERTAIN

    async def _classify_llm(self, text: str) -> Intent:
        """
        LLM-based classification for UNCERTAIN cases (Tier 3).
        Sends a fast classification prompt to Cerebras.
        """
        if not self._llm_service or not self._use_llm_fallback:
            return Intent.UNCERTAIN

        try:
            prompt = _CLASSIFY_PROMPT.format(text=text[:200])

            # Use the LLM service directly for a single-turn classification
            from pipecat.services.cerebras.llm import CerebrasLLMService

            if isinstance(self._llm_service, CerebrasLLMService):
                import httpx

                # Direct API call — faster than going through the pipeline
                response = await self._llm_service._client.chat.completions.create(
                    model=self._llm_service._settings.model,
                    messages=[
                        {"role": "system", "content": "You are a classifier. Respond with exactly one word."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=5,
                    temperature=0.0,
                )
                content = response.choices[0].message.content
                if content is None:
                    logger.warning(
                        "[IntentClassifier] LLM returned None content for '{}'",
                        text[:60],
                    )
                    return Intent.UNCERTAIN
                result = content.strip().upper()

                if "ASSISTANT" in result:
                    logger.info(
                        "[IntentClassifier] LLM classified as DIRECTED: '{}'",
                        text[:60],
                    )
                    return Intent.DIRECTED_TO_ASSISTANT
                elif "BACKGROUND" in result:
                    logger.info(
                        "[IntentClassifier] LLM classified as BACKGROUND: '{}'",
                        text[:60],
                    )
                    return Intent.BACKGROUND_CONVERSATION
                else:
                    logger.warning(
                        "[IntentClassifier] LLM returned unexpected: '{}' for '{}'",
                        result,
                        text[:60],
                    )
                    return Intent.UNCERTAIN

        except Exception as e:
            logger.error("[IntentClassifier] LLM classification failed: {}", e)
            return Intent.UNCERTAIN

    def _resolve_uncertain(self) -> bool:
        """
        Decide what to do with UNCERTAIN intent.
        Returns True if the utterance should be suppressed (stay silent).
        """
        return self._uncertain_default == "silence"

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # ── Turn boundaries ──────────────────────────────────────────────
        if isinstance(frame, UserStartedSpeakingFrame):
            self._turn_suppressed = False
            self._current_transcription = None
            await self.push_frame(frame, direction)
            return

        # ── Transcription — the main classification point ────────────────
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if not text:
                await self.push_frame(frame, direction)
                return

            self._current_transcription = text
            self._total_classified += 1

            # Fast classification
            intent = self._classify_fast(text)

            # If UNCERTAIN, try LLM fallback
            if intent == Intent.UNCERTAIN and self._use_llm_fallback:
                intent = await self._classify_llm(text)

            # Decision
            if intent == Intent.DIRECTED_TO_ASSISTANT:
                self._directed_count += 1
                logger.info(
                    "[IntentClassifier] ✅ DIRECTED | '{}' | stats: {}/{}/{}",
                    text[:60],
                    self._directed_count,
                    self._background_count,
                    self._uncertain_count,
                )
                self._turn_suppressed = False
                await self.push_frame(frame, direction)

            elif intent == Intent.BACKGROUND_CONVERSATION:
                self._background_count += 1
                logger.info(
                    "[IntentClassifier] 🔇 BACKGROUND — suppressing | '{}' | stats: {}/{}/{}",
                    text[:60],
                    self._directed_count,
                    self._background_count,
                    self._uncertain_count,
                )
                self._turn_suppressed = True
                # Don't push the frame — downstream never sees this transcription

            elif intent == Intent.UNCERTAIN:
                self._uncertain_count += 1
                should_suppress = self._resolve_uncertain()
                logger.info(
                    "[IntentClassifier] ❓ UNCERTAIN → {} | '{}' | stats: {}/{}/{}",
                    "SUPPRESS" if should_suppress else "PASS",
                    text[:60],
                    self._directed_count,
                    self._background_count,
                    self._uncertain_count,
                )
                if should_suppress:
                    self._turn_suppressed = True
                    # Don't push
                else:
                    self._turn_suppressed = False
                    await self.push_frame(frame, direction)

            return

        # ── UserStoppedSpeaking — suppress if turn was classified as background ──
        if isinstance(frame, UserStoppedSpeakingFrame):
            if self._turn_suppressed:
                logger.debug(
                    "[IntentClassifier] Suppressing UserStoppedSpeaking for background turn"
                )
                # Don't forward — prevents the aggregator from triggering an LLM call
                return
            await self.push_frame(frame, direction)
            return

        # ── LLMMessagesAppendFrame — suppress if turn was classified as background ──
        if isinstance(frame, LLMMessagesAppendFrame):
            if self._turn_suppressed:
                logger.debug(
                    "[IntentClassifier] Suppressing LLMMessagesAppend for background turn"
                )
                return
            await self.push_frame(frame, direction)
            return

        # ── Everything else passes through ───────────────────────────────
        await self.push_frame(frame, direction)
