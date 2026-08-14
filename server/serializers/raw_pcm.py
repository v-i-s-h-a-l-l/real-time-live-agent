import json

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InputTransportMessageFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer

from config import MAX_PCM_ACCUMULATOR_BYTES, SAMPLE_RATE

_TARGET_BYTES = 1024  # 512 samples × 2 bytes = 1024 bytes for Silero at 16 kHz
_CHANNELS = 1


class RawPCMSerializer(FrameSerializer):
    """Per-connection PCM re-chunker: buffers incoming bytes until _TARGET_BYTES.

    This runs on every audio frame in both directions, so it stays free of
    per-frame logging and other blocking work.
    """

    def __init__(self, **kwargs):
        # RTVI control messages must reach the browser (bot-started-speaking, etc.)
        params = FrameSerializer.InputParams(ignore_rtvi_messages=False)
        super().__init__(params=params, **kwargs)
        self._accumulator = bytearray()

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if self.should_ignore_frame(frame):
            return None
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio
        if isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            try:
                return json.dumps(frame.message)
            except (TypeError, ValueError) as exc:
                # Dropping this silently would lose a bot-state event the UI
                # depends on, with no trace of why.
                logger.warning("[RawPCM] could not serialize control message: {}", exc)
                return None
        return None

    async def deserialize(self, data: bytes | str) -> Frame | None:
        if isinstance(data, bytes):
            if len(data) > MAX_PCM_ACCUMULATOR_BYTES:
                self._accumulator.clear()
                return None
            self._accumulator.extend(data)
            if len(self._accumulator) > MAX_PCM_ACCUMULATOR_BYTES:
                self._accumulator.clear()
                return None
            if len(self._accumulator) < _TARGET_BYTES:
                return None  # not enough yet, wait for more
            chunk = bytes(self._accumulator[:_TARGET_BYTES])
            del self._accumulator[:_TARGET_BYTES]
            return InputAudioRawFrame(
                audio=chunk,
                sample_rate=SAMPLE_RATE,
                num_channels=_CHANNELS,
            )
        if isinstance(data, str):
            # A text/JSON message from the browser signals a control event (e.g.
            # start-speaking, interruption). Flush any partially accumulated audio
            # so stale bytes from the previous turn don't bleed into the next one
            # and cause garbled STT transcriptions.
            self._accumulator.clear()
            try:
                return InputTransportMessageFrame(message=json.loads(data))
            except ValueError as exc:
                logger.debug("[RawPCM] ignoring malformed control frame: {}", exc)
                return None
        return None

