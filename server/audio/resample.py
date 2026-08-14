"""Fast streaming resampling between pipeline (16 kHz) and RNNoise (48 kHz).

Uses integer 3× up/down sampling — no FFT, minimal latency.
"""

from __future__ import annotations

import numpy as np

PIPELINE_SAMPLE_RATE = 16000
RNNOISE_SAMPLE_RATE = 48000
UP_FACTOR = 3
DOWN_FACTOR = 3


def upsample_16_to_48(pcm_16k: np.ndarray) -> np.ndarray:
    """PCM16 mono 16 kHz → PCM16 mono 48 kHz via linear interpolation."""
    n = len(pcm_16k)
    if n == 0:
        return np.array([], dtype=np.int16)
    if n == 1:
        return np.repeat(pcm_16k, UP_FACTOR)

    x = pcm_16k.astype(np.float32)
    positions = np.linspace(0.0, float(n - 1), n * UP_FACTOR, dtype=np.float32)
    out = np.interp(positions, np.arange(n, dtype=np.float32), x)
    return np.clip(out, -32768, 32767).astype(np.int16)


def downsample_48_to_16(pcm_48k: np.ndarray) -> np.ndarray:
    """PCM16 mono 48 kHz → PCM16 mono 16 kHz via 3-sample box filter."""
    n = (len(pcm_48k) // DOWN_FACTOR) * DOWN_FACTOR
    if n == 0:
        return np.array([], dtype=np.int16)
    grouped = pcm_48k[:n].astype(np.int32).reshape(-1, DOWN_FACTOR)
    return (grouped.sum(axis=1) // DOWN_FACTOR).astype(np.int16)
