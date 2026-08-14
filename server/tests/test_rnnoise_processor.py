"""Tests for optional RNNoise preprocessing."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audio.resample import (
    PIPELINE_SAMPLE_RATE,
    RNNOISE_SAMPLE_RATE,
    downsample_48_to_16,
    upsample_16_to_48,
)
from audio.rnnoise_processor import RNNoiseProcessor


def test_resample_16_to_48_ratio():
    pcm = np.array([1000, -1000, 2000, -2000], dtype=np.int16)
    up = upsample_16_to_48(pcm)
    assert up.dtype == np.int16
    assert len(up) == len(pcm) * 3


def test_resample_roundtrip_length():
    pcm = np.random.randint(-5000, 5000, size=512, dtype=np.int16)
    back = downsample_48_to_16(upsample_16_to_48(pcm))
    assert len(back) == len(pcm)


def test_resample_sample_rates():
    assert PIPELINE_SAMPLE_RATE == 16000
    assert RNNOISE_SAMPLE_RATE == 48000


def test_disabled_passthrough():
    proc = RNNoiseProcessor(enabled=False)
    pcm = np.arange(512, dtype=np.int16)
    out = proc.process(pcm)
    assert np.array_equal(out, pcm)
    assert not proc.initialize()


def test_fallback_on_missing_library():
    proc = RNNoiseProcessor(enabled=True, session_id="test-fallback")
    with patch("audio.rnnoise_native.library_available", return_value=False):
        assert proc.initialize() is False
    assert proc.using_fallback
    pcm = np.arange(256, dtype=np.int16)
    assert np.array_equal(proc.process(pcm), pcm)


def test_process_output_same_length():
    proc = RNNoiseProcessor(enabled=True, session_id="test-len")

    def fake_create():
        return object()

    def fake_destroy(_state):
        return None

    def fake_process(_state, frame):
        return frame.copy(), 0.9

    with patch("audio.rnnoise_native.library_available", return_value=True), patch(
        "audio.rnnoise_native.create", side_effect=fake_create
    ), patch("audio.rnnoise_native.destroy", side_effect=fake_destroy), patch(
        "audio.rnnoise_native.FRAME_SIZE", 480
    ), patch(
        "audio.rnnoise_native.process_mono_frame", side_effect=fake_process
    ):
        assert proc.initialize() is True
        for _ in range(5):
            chunk = np.random.randint(-8000, 8000, size=512, dtype=np.int16)
            out = proc.process(chunk)
            assert len(out) == len(chunk)
            assert out.dtype == np.int16


def test_reset_clears_buffers():
    proc = RNNoiseProcessor(enabled=False)
    proc._buf_48k = np.array([1, 2, 3], dtype=np.int16)
    proc._pending_16k = np.array([4, 5], dtype=np.int16)
    proc.reset()
    assert len(proc._buf_48k) == 0
    assert len(proc._pending_16k) == 0


def test_concurrent_sessions_isolated_state():
    a = RNNoiseProcessor(enabled=False, session_id="a")
    b = RNNoiseProcessor(enabled=False, session_id="b")
    a._pending_16k = np.array([1], dtype=np.int16)
    assert len(b._pending_16k) == 0


def test_processing_error_enters_fallback():
    proc = RNNoiseProcessor(enabled=True, session_id="err")

    with patch("audio.rnnoise_native.library_available", return_value=True), patch(
        "audio.rnnoise_native.create", return_value=object()
    ), patch("audio.rnnoise_native.destroy"), patch(
        "audio.rnnoise_native.FRAME_SIZE", 480
    ), patch(
        "audio.resample.upsample_16_to_48", side_effect=RuntimeError("boom")
    ):
        proc.initialize()
        pcm = np.zeros(512, dtype=np.int16)
        out = proc.process(pcm)
        assert np.array_equal(out, pcm)
        assert proc.using_fallback


@pytest.mark.skipif(
    not __import__("audio.rnnoise_native", fromlist=["library_available"]).library_available(),
    reason="RNNoise native library not installed",
)
def test_native_initialize_and_frame():
    from audio import rnnoise_native

    proc = RNNoiseProcessor(enabled=True, session_id="native")
    assert proc.initialize() is True
    assert rnnoise_native.FRAME_SIZE == 480

    silence = np.zeros(512, dtype=np.int16)
    out = proc.process(silence)
    assert len(out) == 512
    proc.close()
