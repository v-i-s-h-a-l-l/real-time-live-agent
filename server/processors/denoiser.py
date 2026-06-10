"""
RNNoiseDenoiserProcessor
────────────────────────
Real-time noise suppression using RNNoise (via pyrnnoise).

RNNoise operates at 48 kHz with a fixed 480-sample (10 ms) frame size.
Since the pipeline runs at 16 kHz, this processor:
  1. Resamples incoming 16 kHz PCM → 48 kHz
  2. Buffers into 480-sample frames
  3. Runs RNNoise on each frame
  4. Resamples the denoised 48 kHz audio back → 16 kHz
  5. Pushes the cleaned audio downstream

Place this AFTER audio_gate and BEFORE vad in the pipeline.
"""

import numpy as np
from scipy import signal as scipy_signal

from loguru import logger

from pipecat.frames.frames import (
    Frame,
    AudioRawFrame,
    InterruptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


# RNNoise constants
_RNNOISE_SAMPLE_RATE = 48000
_RNNOISE_FRAME_SIZE = 480  # 10 ms at 48 kHz


class RNNoiseDenoiserProcessor(FrameProcessor):
    """
    Pipecat FrameProcessor that denoises audio using RNNoise.

    Args:
        pipeline_sample_rate:
            Sample rate of the pipeline audio (default 16000).
        enabled:
            Set False to bypass denoising (passthrough mode).
    """

    def __init__(
        self,
        *,
        pipeline_sample_rate: int = 16000,
        enabled: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._pipeline_sr = pipeline_sample_rate
        self._enabled = enabled
        self._denoiser = None  # lazy init on first audio frame

        # Resample ratios (16kHz ↔ 48kHz)
        self._up_ratio = _RNNOISE_SAMPLE_RATE / self._pipeline_sr  # 3.0
        self._down_ratio = self._pipeline_sr / _RNNOISE_SAMPLE_RATE  # 0.333...

        # Buffer for accumulating 48kHz samples until we have a full 480-sample frame
        self._buffer_48k = np.array([], dtype=np.int16)

        # Output buffer for accumulating denoised 48kHz samples before downsampling
        self._output_48k = np.array([], dtype=np.int16)

        self._frame_count = 0

        logger.info(
            "[RNNoiseDenoiser] Initialized | pipeline_sr={} enabled={}",
            self._pipeline_sr,
            self._enabled,
        )

    def _ensure_denoiser(self):
        """Lazy-init RNNoise on first use to avoid import-time overhead."""
        if self._denoiser is None:
            from pyrnnoise import RNNoise
            self._denoiser = RNNoise(sample_rate=_RNNOISE_SAMPLE_RATE)
            logger.info("[RNNoiseDenoiser] RNNoise model loaded (48kHz)")

    def _reset_buffers(self):
        """Clear all internal buffers."""
        self._buffer_48k = np.array([], dtype=np.int16)
        self._output_48k = np.array([], dtype=np.int16)

    def _resample_up(self, pcm_16k: np.ndarray) -> np.ndarray:
        """Resample 16kHz int16 → 48kHz int16."""
        if len(pcm_16k) == 0:
            return np.array([], dtype=np.int16)

        # Convert to float for resampling
        float_data = pcm_16k.astype(np.float64)
        target_len = int(len(float_data) * self._up_ratio)
        resampled = scipy_signal.resample(float_data, target_len)
        return np.clip(resampled, -32768, 32767).astype(np.int16)

    def _resample_down(self, pcm_48k: np.ndarray) -> np.ndarray:
        """Resample 48kHz int16 → 16kHz int16."""
        if len(pcm_48k) == 0:
            return np.array([], dtype=np.int16)

        float_data = pcm_48k.astype(np.float64)
        target_len = int(len(float_data) * self._down_ratio)
        resampled = scipy_signal.resample(float_data, target_len)
        return np.clip(resampled, -32768, 32767).astype(np.int16)

    def _denoise_buffer(self) -> np.ndarray:
        """
        Process all complete 480-sample frames in the buffer through RNNoise.
        Returns denoised 48kHz int16 samples. Leftover samples stay in buffer.
        """
        n_samples = len(self._buffer_48k)
        n_frames = n_samples // _RNNOISE_FRAME_SIZE
        if n_frames == 0:
            return np.array([], dtype=np.int16)

        usable = n_frames * _RNNOISE_FRAME_SIZE
        to_process = self._buffer_48k[:usable]
        self._buffer_48k = self._buffer_48k[usable:]  # keep remainder

        # pyrnnoise expects shape (channels, samples) — mono = (1, N)
        chunk = to_process.reshape(1, -1)
        denoised_parts = []

        for _vad_prob, denoised_frame in self._denoiser.denoise_chunk(chunk):
            # denoised_frame shape: (1, 480)
            denoised_parts.append(denoised_frame.squeeze(0))

        if denoised_parts:
            return np.concatenate(denoised_parts).astype(np.int16)
        return np.array([], dtype=np.int16)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # ── Passthrough if disabled ──────────────────────────────────────
        if not self._enabled:
            await self.push_frame(frame, direction)
            return

        # ── Audio frame — denoise it ─────────────────────────────────────
        if isinstance(frame, AudioRawFrame):
            try:
                self._ensure_denoiser()

                # Decode incoming PCM bytes → int16
                pcm_16k = np.frombuffer(frame.audio, dtype=np.int16)

                # Upsample 16kHz → 48kHz
                pcm_48k = self._resample_up(pcm_16k)

                # Add to buffer
                self._buffer_48k = np.concatenate([self._buffer_48k, pcm_48k])

                # Process all complete frames
                denoised_48k = self._denoise_buffer()

                if len(denoised_48k) > 0:
                    # Downsample 48kHz → 16kHz
                    denoised_16k = self._resample_down(denoised_48k)

                    # Mutate the original frame in-place to preserve Pipecat
                    # internal attributes (id, broadcast_sibling_id, etc.)
                    frame.audio = denoised_16k.tobytes()
                    await self.push_frame(frame, direction)

                    self._frame_count += 1
                    if self._frame_count == 1:
                        logger.info("[RNNoiseDenoiser] First denoised frame emitted")
                    elif self._frame_count % 500 == 0:
                        logger.debug(
                            "[RNNoiseDenoiser] {} frames denoised, buffer_remainder={}",
                            self._frame_count,
                            len(self._buffer_48k),
                        )

                # If no complete frames yet, hold — audio will be emitted
                # once enough samples accumulate (max ~10ms latency)

            except Exception as e:
                logger.warning(
                    "[RNNoiseDenoiser] Denoise failed, passing through: {}", e
                )
                await self.push_frame(frame, direction)
            return

        # ── Interruption — flush buffers ─────────────────────────────────
        if isinstance(frame, InterruptionFrame):
            self._reset_buffers()
            await self.push_frame(frame, direction)
            return

        # ── Everything else passes through ───────────────────────────────
        await self.push_frame(frame, direction)
