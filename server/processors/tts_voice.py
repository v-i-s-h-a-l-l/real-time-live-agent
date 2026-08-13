"""Apply a student-selected Cartesia voice without touching language tracking."""

from __future__ import annotations

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputTransportMessageFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TextFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService

from processors.session_context import SessionContextStore
from protocol import CLIENT_TTS_VOICE, is_client_message
from voices import ALLOWED_TTS_VOICES, resolve_tts_voice_id


class TtsVoiceProcessor(FrameProcessor):
    """Consume `{type: tts_voice, voiceId}` and remember it on the session store."""

    def __init__(self, store: SessionContextStore, *, session_id: str = "-", **kwargs):
        super().__init__(**kwargs)
        self._store = store
        self._session_id = session_id

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputTransportMessageFrame):
            msg = frame.message
            if is_client_message(msg, CLIENT_TTS_VOICE):
                raw = msg.get("voiceId") or msg.get("voice")
                if not raw or str(raw) not in ALLOWED_TTS_VOICES:
                    logger.warning(
                        "[TtsVoice] ignored unknown voice | session={} raw={}",
                        self._session_id,
                        raw,
                    )
                    return
                voice_id = str(raw)
                self._store.tts_voice_id = voice_id
                logger.info(
                    "[TtsVoice] selected | session={} voice={} name={}",
                    self._session_id,
                    voice_id,
                    ALLOWED_TTS_VOICES[voice_id],
                )
                await self.push_frame(
                    TTSUpdateSettingsFrame(
                        delta=CartesiaTTSService.Settings(voice=voice_id)
                    ),
                    direction,
                )
                return

        await self.push_frame(frame, direction)


class TtsApplyVoiceProcessor(FrameProcessor):
    """Re-assert the selected voice immediately before Cartesia, once per change."""

    def __init__(self, store: SessionContextStore, *, session_id: str = "-", **kwargs):
        super().__init__(**kwargs)
        self._store = store
        self._session_id = session_id
        self._applied: str | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InterruptionFrame):
            self._store.skip_tts_next_response = False

        if self._store.skip_tts_next_response and isinstance(
            frame, (TextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame)
        ):
            frame.skip_tts = True
            if isinstance(frame, LLMFullResponseEndFrame):
                self._store.skip_tts_next_response = False

        if isinstance(frame, (LLMFullResponseStartFrame, TTSUpdateSettingsFrame)):
            voice_id = resolve_tts_voice_id(self._store.tts_voice_id)
            if voice_id != self._applied:
                self._applied = voice_id
                logger.info(
                    "[TtsVoice] applying before TTS | session={} voice={} name={}",
                    self._session_id,
                    voice_id,
                    ALLOWED_TTS_VOICES.get(voice_id, "unknown"),
                )
                await self.push_frame(
                    TTSUpdateSettingsFrame(
                        delta=CartesiaTTSService.Settings(voice=voice_id)
                    ),
                    direction,
                )

        await self.push_frame(frame, direction)
