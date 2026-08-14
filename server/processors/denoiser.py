"""
RNNoiseDenoiserProcessor
────────────────────────
Optional Pipecat stage: AudioGate → **RNNoise** → Silero VAD → STT.

Delegates all DSP to ``RNNoiseProcessor`` (isolated, per-session, fail-safe).
"""

from __future__ import annotations

import numpy as np
from loguru import logger

from pipecat.frames.frames import AudioRawFrame, Frame, InterruptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from audio.rnnoise_processor import RNNoiseProcessor
from ops_log import ops_event


class RNNoiseDenoiserProcessor(FrameProcessor):
    """Thin Pipecat wrapper around :class:`RNNoiseProcessor`."""

    def __init__(
        self,
        *,
        pipeline_sample_rate: int = 16000,
        enabled: bool = False,
        session_id: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._pipeline_sr = pipeline_sample_rate
        self._processor = RNNoiseProcessor(enabled=enabled, session_id=session_id)
        self._frames_emitted = 0

        ops_event(
            "rnnoise_enabled" if enabled else "rnnoise_disabled",
            session_id=session_id,
            category="audio",
            pipeline_sample_rate=pipeline_sample_rate,
        )
        logger.info(
            "[RNNoiseDenoiser] Initialized | pipeline_sr={} enabled={}",
            self._pipeline_sr,
            enabled,
        )

    @property
    def enabled(self) -> bool:
        return self._processor.enabled

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not self._processor.enabled and not isinstance(frame, InterruptionFrame):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InterruptionFrame):
            self._processor.reset()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, AudioRawFrame):
            pcm_16k = np.frombuffer(frame.audio, dtype=np.int16)
            cleaned = self._processor.process(pcm_16k)
            frame.audio = cleaned.tobytes()
            await self.push_frame(frame, direction)

            self._frames_emitted += 1
            if self._frames_emitted == 1 and self._processor.initialized:
                logger.info("[RNNoiseDenoiser] First denoised frame emitted")
            return

        await self.push_frame(frame, direction)

    def close(self) -> None:
        self._processor.close()
