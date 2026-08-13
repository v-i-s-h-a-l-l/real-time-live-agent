"""Audio framing and control-frame handling on the browser socket.

This serializer sits on the hot path for every audio frame, so the tests
pin the two behaviours the rest of the pipeline depends on: fixed-size
chunks for the VAD, and a buffer flush when a control message arrives so
stale audio from the previous turn cannot bleed into the next one.
"""

import asyncio
import sys
from pathlib import Path

from pipecat.frames.frames import InputAudioRawFrame, InputTransportMessageFrame

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import SAMPLE_RATE  # noqa: E402
from serializers.raw_pcm import _TARGET_BYTES, RawPCMSerializer  # noqa: E402


def _deserialize(serializer: RawPCMSerializer, data: bytes | str):
    return asyncio.run(serializer.deserialize(data))


def test_audio_is_buffered_until_a_full_chunk_is_available():
    serializer = RawPCMSerializer()
    assert _deserialize(serializer, b"\x00" * (_TARGET_BYTES - 2)) is None

    frame = _deserialize(serializer, b"\x00\x00")
    assert isinstance(frame, InputAudioRawFrame)
    assert len(frame.audio) == _TARGET_BYTES


def test_chunks_are_emitted_at_the_pipeline_sample_rate():
    serializer = RawPCMSerializer()
    frame = _deserialize(serializer, b"\x01" * _TARGET_BYTES)
    assert isinstance(frame, InputAudioRawFrame)
    assert frame.sample_rate == SAMPLE_RATE
    assert frame.num_channels == 1


def test_leftover_audio_is_kept_for_the_next_chunk():
    serializer = RawPCMSerializer()
    frame = _deserialize(serializer, b"\x02" * (_TARGET_BYTES + 10))
    assert isinstance(frame, InputAudioRawFrame)
    assert _deserialize(serializer, b"") is None  # 10 bytes still buffered
    assert _deserialize(serializer, b"\x02" * (_TARGET_BYTES - 10)) is not None


def test_control_message_becomes_a_transport_frame():
    serializer = RawPCMSerializer()
    frame = _deserialize(serializer, '{"type": "interrupt"}')
    assert isinstance(frame, InputTransportMessageFrame)
    assert frame.message == {"type": "interrupt"}


def test_control_message_drops_stale_audio_from_the_previous_turn():
    serializer = RawPCMSerializer()
    _deserialize(serializer, b"\x03" * (_TARGET_BYTES - 4))
    _deserialize(serializer, '{"type": "interrupt"}')

    # The partial chunk is gone, so the next full chunk starts clean.
    assert _deserialize(serializer, b"\x04" * (_TARGET_BYTES - 4)) is None
    frame = _deserialize(serializer, b"\x04" * 4)
    assert isinstance(frame, InputAudioRawFrame)
    assert frame.audio == b"\x04" * _TARGET_BYTES


def test_malformed_control_frame_is_ignored_rather_than_crashing():
    serializer = RawPCMSerializer()
    assert _deserialize(serializer, "{not json") is None
