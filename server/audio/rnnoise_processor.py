"""Isolated RNNoise preprocessing — one state per voice session."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from audio.resample import downsample_48_to_16, upsample_16_to_48
from ops_log import ops_event

if TYPE_CHECKING:
    import ctypes


@dataclass
class RNNoiseStats:
    frames_processed: int = 0
    total_process_us: int = 0
    fallback_count: int = 0

    @property
    def avg_process_us(self) -> float:
        if self.frames_processed == 0:
            return 0.0
        return self.total_process_us / self.frames_processed


class RNNoiseProcessor:
    """Per-session RNNoise state with streaming 16 kHz ↔ 48 kHz boundary."""

    def __init__(self, *, enabled: bool = True, session_id: str | None = None):
        self._enabled = enabled
        self._session_id = session_id
        self._state: ctypes.c_void_p | None = None
        self._frame_size = 480
        self._initialized = False
        self._fallback = False
        self._buf_48k = np.array([], dtype=np.int16)
        self._pending_16k = np.array([], dtype=np.int16)
        self.stats = RNNoiseStats()

    @property
    def enabled(self) -> bool:
        return self._enabled and not self._fallback

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def using_fallback(self) -> bool:
        return self._fallback

    def initialize(self) -> bool:
        """Load native RNNoise once per session. Fail-safe → passthrough."""
        if not self._enabled:
            return False
        if self._initialized:
            return True

        try:
            from audio import rnnoise_native

            if not rnnoise_native.library_available():
                raise OSError("RNNoise library not installed")

            self._state = rnnoise_native.create()
            self._frame_size = rnnoise_native.FRAME_SIZE
            self._initialized = True
            ops_event(
                "rnnoise_initialized",
                session_id=self._session_id,
                category="audio",
                frame_size=self._frame_size,
            )
            return True
        except Exception as exc:
            self._enter_fallback("init_failed", error_type=type(exc).__name__)
            return False

    def _enter_fallback(self, reason: str, **extra) -> None:
        if not self._fallback:
            self._fallback = True
            self._enabled = False
            ops_event(
                "rnnoise_fallback",
                session_id=self._session_id,
                category="audio",
                reason=reason,
                **extra,
            )
        self.close()

    def process(self, pcm_16k: np.ndarray) -> np.ndarray:
        """Return PCM16 mono @ 16 kHz, same length as input."""
        if pcm_16k.size == 0:
            return pcm_16k

        if not self._enabled or self._fallback:
            return pcm_16k

        if not self._initialized:
            if not self.initialize():
                return pcm_16k

        assert self._state is not None

        try:
            t0 = time.perf_counter()

            pcm_48k = upsample_16_to_48(pcm_16k)
            if pcm_48k.size:
                self._buf_48k = np.concatenate((self._buf_48k, pcm_48k))

            from audio.rnnoise_native import process_mono_frame

            denoised_parts: list[np.ndarray] = []
            while len(self._buf_48k) >= self._frame_size:
                frame = self._buf_48k[: self._frame_size]
                self._buf_48k = self._buf_48k[self._frame_size :]
                out, _ = process_mono_frame(self._state, frame)
                denoised_parts.append(out)

            if denoised_parts:
                denoised_48k = np.concatenate(denoised_parts)
                self._pending_16k = np.concatenate(
                    (self._pending_16k, downsample_48_to_16(denoised_48k))
                )

            n_in = len(pcm_16k)
            if len(self._pending_16k) >= n_in:
                result = self._pending_16k[:n_in].copy()
                self._pending_16k = self._pending_16k[n_in:]
            elif len(self._pending_16k) > 0:
                result = pcm_16k.copy()
                n = len(self._pending_16k)
                result[:n] = self._pending_16k
                self._pending_16k = np.array([], dtype=np.int16)
            else:
                result = pcm_16k

            elapsed_us = int((time.perf_counter() - t0) * 1_000_000)
            self.stats.frames_processed += 1
            self.stats.total_process_us += elapsed_us
            return result

        except Exception as exc:
            self.stats.fallback_count += 1
            ops_event(
                "rnnoise_processing_error",
                session_id=self._session_id,
                category="audio",
                error_type=type(exc).__name__,
            )
            self._enter_fallback("processing_error", error_type=type(exc).__name__)
            return pcm_16k

    def reset(self) -> None:
        """Clear streaming buffers (e.g. on interruption). Keep RNNoise state."""
        self._buf_48k = np.array([], dtype=np.int16)
        self._pending_16k = np.array([], dtype=np.int16)

    def close(self) -> None:
        if self._state is not None:
            from audio.rnnoise_native import destroy

            destroy(self._state)
            self._state = None
        self._initialized = False
        self.reset()
