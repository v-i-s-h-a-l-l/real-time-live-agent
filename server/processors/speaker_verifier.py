"""
SpeakerVerifier
───────────────
Lightweight speaker enrollment + verification using resemblyzer.

Usage:
    verifier = SpeakerVerifier()
    verifier.enroll(audio_bytes, sample_rate=16000)
    is_match, score = verifier.verify(audio_bytes, sample_rate=16000)

The model (~5 MB) runs on CPU with 30–80 ms per embedding.
"""

import asyncio
import numpy as np
from loguru import logger

_encoder = None  # lazy-loaded singleton


def _get_encoder():
    """Lazy-load the VoiceEncoder once across the process."""
    global _encoder
    if _encoder is None:
        from resemblyzer import VoiceEncoder

        _encoder = VoiceEncoder(device="cpu")
        logger.info("[SpeakerVerifier] VoiceEncoder loaded (CPU)")
    return _encoder


def _pcm16_bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    """Convert PCM-16 LE bytes → float32 numpy array normalised to [-1, 1]."""
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    return samples / 32768.0


class SpeakerVerifier:
    """
    Enroll a speaker's voiceprint, then verify subsequent audio against it.

    Thread-safe: uses an asyncio lock around the encoder so concurrent
    pipeline tasks don't collide.
    """

    def __init__(self, similarity_threshold: float = 0.75):
        self._threshold = similarity_threshold
        self._enrolled_embedding: np.ndarray | None = None
        self._lock = asyncio.Lock()
        self._is_enrolled = False
        logger.info(
            "[SpeakerVerifier] Initialized | threshold={}",
            similarity_threshold,
        )

    @property
    def is_enrolled(self) -> bool:
        return self._is_enrolled

    async def enroll(self, audio_bytes: bytes, sample_rate: int = 16000) -> bool:
        """
        Enroll the primary speaker from raw PCM-16 audio.

        Returns True if enrollment succeeded (enough audio, valid embedding).
        """
        async with self._lock:
            try:
                wav = _pcm16_bytes_to_float32(audio_bytes)
                if len(wav) < sample_rate:  # need at least 1s
                    logger.warning(
                        "[SpeakerVerifier] Enrollment audio too short: {:.1f}s",
                        len(wav) / sample_rate,
                    )
                    return False

                encoder = _get_encoder()
                # resemblyzer expects float32 array, sample_rate via preprocess_wav
                from resemblyzer import preprocess_wav

                wav_processed = preprocess_wav(wav, source_sr=sample_rate)
                self._enrolled_embedding = encoder.embed_utterance(wav_processed)
                self._is_enrolled = True

                logger.info(
                    "[SpeakerVerifier] Enrolled speaker | audio={:.1f}s embedding_shape={}",
                    len(wav) / sample_rate,
                    self._enrolled_embedding.shape,
                )
                return True
            except Exception as e:
                logger.error("[SpeakerVerifier] Enrollment failed: {}", e)
                return False

    async def verify(
        self, audio_bytes: bytes, sample_rate: int = 16000
    ) -> tuple[bool, float]:
        """
        Verify audio against the enrolled speaker.

        Returns:
            (is_match, similarity_score)
            is_match is True if similarity >= threshold.
            If not enrolled, returns (True, 1.0) — open gate.
        """
        if not self._is_enrolled:
            return True, 1.0

        async with self._lock:
            try:
                wav = _pcm16_bytes_to_float32(audio_bytes)
                if len(wav) < sample_rate * 0.3:  # need at least 0.3s
                    # Too short to verify reliably — let it through
                    return True, 1.0

                encoder = _get_encoder()
                from resemblyzer import preprocess_wav

                wav_processed = preprocess_wav(wav, source_sr=sample_rate)
                embedding = encoder.embed_utterance(wav_processed)

                # Cosine similarity
                similarity = float(
                    np.dot(self._enrolled_embedding, embedding)
                    / (
                        np.linalg.norm(self._enrolled_embedding)
                        * np.linalg.norm(embedding)
                        + 1e-8
                    )
                )

                is_match = similarity >= self._threshold
                return is_match, similarity

            except Exception as e:
                logger.error("[SpeakerVerifier] Verification failed: {}", e)
                # On error, let audio through (fail-open)
                return True, 1.0
