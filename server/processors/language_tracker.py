"""
LanguageTrackerProcessor
────────────────────────
Single source of truth for the conversation's active language.

Reads Sarvam ``TranscriptionFrame.language`` + script heuristics, plus typed
chat via ``observe_utterance``. Applies hysteresis so one stray word can't
flip the language, keeps Indic sessions sticky across Roman Hinglish/Tanglish,
and honours explicit "switch to <language>" requests immediately. Tracks
Roman vs native script so replies match how the student is typing.

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
    INDIC_LANGUAGES,
    LANG_EN,
    SCRIPT_NATIVE,
    SCRIPT_ROMAN,
    detect_language_request,
    detect_romanized_indic_language,
    detect_script_mode,
    display_name,
    looks_like_full_english,
    looks_like_romanized_indic,
    resolve_detected_language,
    significant_char_count,
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
        self._script = SCRIPT_ROMAN
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

    @property
    def current_script(self) -> str:
        return self._script

    def _maybe_update_script(self, text: str) -> None:
        mode = detect_script_mode(text)
        if mode is None:
            return
        if mode == SCRIPT_NATIVE:
            self._script = SCRIPT_NATIVE
            return
        # Roman: ignore short acks so "ok"/"yes" cannot flip a native-script session.
        if significant_char_count(text) >= self._min_chars:
            self._script = SCRIPT_ROMAN

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
            await self._maybe_switch(frame)

        await self.push_frame(frame, direction)

    async def observe_utterance(
        self,
        text: str,
        *,
        sarvam_language: object | None = None,
    ) -> None:
        """Update session language/script from voice STT or typed chat."""
        text = (text or "").strip()
        if not text:
            return

        # 1. Explicit user preference ("talk in English", "हिंदी में बताओ")
        #    overrides automatic detection and bypasses the hysteresis window.
        requested = detect_language_request(text)
        if requested:
            self._maybe_update_script(text)
            if requested != self._current:
                await self._apply_switch(
                    requested, source="explicit", confidence=1.0, sample=text
                )
                return
            self._pending = None
            self._pending_count = 0
            return

        # 2. Automatic detection from Sarvam tag + script.
        detected, confidence, source = resolve_detected_language(
            text=text,
            sarvam_language=sarvam_language,
            min_chars=self._min_chars,
            min_confidence=self._min_confidence,
        )

        # A substantive Roman-Indic clause is a clear switch signal, even when
        # Sarvam / script say English. This is the "clear-switch overrides
        # sticky" rule — several Hindi/Tamil/Telugu tokens beat the fallback.
        roman_indic = detect_romanized_indic_language(text)
        if roman_indic and roman_indic != self._current:
            detected = roman_indic
            confidence = max(confidence, 0.9)
            source = "roman-indic"
        elif (
            self._current in INDIC_LANGUAGES
            and detected == LANG_EN
            and (
                looks_like_romanized_indic(text)
                or not looks_like_full_english(text)
            )
        ):
            # Latin / Sarvam-English while already in an Indic language is
            # usually Hinglish/Tanglish, not a switch back to English.
            detected = self._current
            source = "sticky"

        if (
            significant_char_count(text) >= self._min_chars
            or detect_script_mode(text) == SCRIPT_NATIVE
        ):
            self._maybe_update_script(text)

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

    async def _maybe_switch(self, frame: TranscriptionFrame) -> None:
        await self.observe_utterance(
            frame.text or "",
            sarvam_language=getattr(frame, "language", None),
        )

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
