"""
LanguageTrackerProcessor
────────────────────────
Single source of truth for the conversation's active language.

Reads Sarvam ``TranscriptionFrame.language`` + script heuristics, applies
hysteresis so one stray word can't flip the language, and honours explicit
"switch to <language>" requests immediately. The active language it holds is
read every turn by the Tutor Engine directive, so the reply language is
reasserted on *every* turn — not only when the language changes.

It updates Cartesia's TTS language on a real switch and never blocks the stream.
The reply-language instruction itself lives in the per-turn tutor directive, so
this processor no longer appends system messages to the context.
"""

from __future__ import annotations

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService

from languages import (
    LANG_EN,
    detect_language_request,
    display_name,
    resolve_detected_language,
    to_cartesia_language,
)


class LanguageTrackerProcessor(FrameProcessor):
    def __init__(
        self,
        *,
        context: LLMContext,
        session_id: str = "-",
        initial_language: str = LANG_EN,
        min_chars: int = 8,
        min_confidence: float = 0.55,
        confirmations_needed: int = 1,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._context = context
        self._session_id = session_id
        self._current = initial_language or LANG_EN
        self._min_chars = min_chars
        self._min_confidence = min_confidence
        self._confirmations_needed = max(1, confirmations_needed)
        self._pending: str | None = None
        self._pending_count = 0
        self._initialized_log = False

        logger.info(
            "[Language] session={} initial={} (auto-detect active)",
            self._session_id,
            display_name(self._current),
        )

    @property
    def current_language(self) -> str:
        return self._current

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
            await self._maybe_switch(frame)

        await self.push_frame(frame, direction)

    async def _maybe_switch(self, frame: TranscriptionFrame) -> None:
        text = (frame.text or "").strip()

        # 1. Explicit user preference ("talk in English", "हिंदी में बताओ")
        #    overrides automatic detection and bypasses the hysteresis window.
        requested = detect_language_request(text)
        if requested and requested != self._current:
            await self._apply_switch(
                requested, source="explicit", confidence=1.0, sample=text
            )
            return
        if requested:
            # Already speaking it — clear any pending drift toward another language.
            self._pending = None
            self._pending_count = 0
            return

        # 2. Automatic detection from Sarvam tag + script.
        detected, confidence, source = resolve_detected_language(
            text=text,
            sarvam_language=getattr(frame, "language", None),
            min_chars=self._min_chars,
            min_confidence=self._min_confidence,
        )

        if not self._initialized_log and detected:
            logger.info(
                "[Language] Detected language: {} | session={} source={} conf={:.2f} text={!r}",
                display_name(detected),
                self._session_id,
                source,
                confidence,
                text[:80],
            )
            self._initialized_log = True

        # Weak / short / ambiguous evidence never disturbs the active language.
        if not detected or detected == self._current:
            self._pending = None
            self._pending_count = 0
            return

        # Hysteresis: require N consecutive confident detections of the new
        # language before switching, so a single code-switched clause holds.
        # Unambiguous evidence — a full clause in a new script, or Sarvam and the
        # script agreeing — is a deliberate switch and applies at once.
        strong = confidence >= 0.9 or source == "sarvam+script"
        if detected == self._pending:
            self._pending_count += 1
        else:
            self._pending = detected
            self._pending_count = 1

        if not strong and self._pending_count < self._confirmations_needed:
            logger.info(
                "[Language] holding {} — pending {} ({}/{}) | session={}",
                display_name(self._current),
                display_name(detected),
                self._pending_count,
                self._confirmations_needed,
                self._session_id,
            )
            return

        await self._apply_switch(detected, source=source, confidence=confidence, sample=text)

    async def _apply_switch(
        self,
        new_lang: str,
        *,
        source: str,
        confidence: float,
        sample: str,
    ) -> None:
        old = self._current
        self._current = new_lang
        self._pending = None
        self._pending_count = 0

        logger.info(
            "[Language] Language switched: {} → {} | session={} source={} conf={:.2f} sample={!r}",
            display_name(old),
            display_name(new_lang),
            self._session_id,
            source,
            confidence,
            sample[:80],
        )

        # Update TTS language for the next spoken reply (non-blocking frame).
        # The reply-language instruction is reasserted every turn by the Tutor
        # Engine directive, so no system message is appended here.
        await self.push_frame(
            TTSUpdateSettingsFrame(
                delta=CartesiaTTSService.Settings(language=to_cartesia_language(new_lang))
            )
        )
