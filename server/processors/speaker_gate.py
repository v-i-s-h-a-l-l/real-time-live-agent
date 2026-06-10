"""
SpeakerGateProcessor
────────────────────
Pipeline processor that gates audio based on speaker identity.

Phase 1 — Enrollment (first ~3 seconds):
    Buffers incoming audio and enrolls the primary speaker's voiceprint.
    All audio passes through during this phase.

Phase 2 — Verification (after enrollment):
    Accumulates a short window of audio per speech segment, runs speaker
    verification once, and caches the decision for the rest of the segment.
    Non-matching audio is silently dropped.

Place this AFTER the VAD in the pipeline so it only runs on speech-detected
frames, not on every silence frame.
"""

import asyncio
from loguru import logger

from pipecat.frames.frames import (
    AudioRawFrame,
    Frame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from processors.speaker_verifier import SpeakerVerifier


class SpeakerGateProcessor(FrameProcessor):
    """
    Gate audio frames based on speaker voiceprint matching.

    Args:
        verifier:                Shared SpeakerVerifier instance.
        enrollment_duration_secs: How many seconds of audio to buffer for enrollment.
        verification_window_secs: How much audio to accumulate before running
                                  verification on a new speech segment.
        sample_rate:             Audio sample rate (must match pipeline).
    """

    def __init__(
        self,
        verifier: SpeakerVerifier,
        enrollment_duration_secs: float = 3.0,
        verification_window_secs: float = 0.8,
        sample_rate: int = 16000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._verifier = verifier
        self._enrollment_secs = enrollment_duration_secs
        self._verification_window_secs = verification_window_secs
        self._sample_rate = sample_rate

        # Enrollment state
        self._enrollment_buffer = bytearray()
        self._enrollment_bytes_needed = int(
            enrollment_duration_secs * sample_rate * 2  # 2 bytes per PCM-16 sample
        )
        self._enrollment_done = False

        # Per-segment verification state
        self._segment_buffer = bytearray()
        self._segment_verified = False
        self._segment_is_match = True  # default: let through until verified
        self._segment_bytes_needed = int(
            verification_window_secs * sample_rate * 2
        )

        # Stats
        self._segments_checked = 0
        self._segments_passed = 0
        self._segments_blocked = 0

        logger.info(
            "[SpeakerGate] Initialized | enrollment={:.1f}s verification_window={:.1f}s",
            enrollment_duration_secs,
            verification_window_secs,
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # ── User turn boundaries ─────────────────────────────────────────
        if isinstance(frame, UserStartedSpeakingFrame):
            # New speech segment — reset per-segment verification
            self._segment_buffer = bytearray()
            self._segment_verified = False
            self._segment_is_match = True  # optimistic until verified
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStoppedSpeakingFrame):
            if self._enrollment_done and self._segments_checked > 0:
                logger.debug(
                    "[SpeakerGate] Segment ended | match={} | "
                    "total: checked={} passed={} blocked={}",
                    self._segment_is_match,
                    self._segments_checked,
                    self._segments_passed,
                    self._segments_blocked,
                )
            # If this segment was blocked, don't forward UserStoppedSpeaking
            # so downstream processors (STT, aggregator) never see the turn.
            if self._enrollment_done and not self._segment_is_match:
                logger.info(
                    "[SpeakerGate] Suppressing UserStoppedSpeaking — non-matching speaker"
                )
                return
            await self.push_frame(frame, direction)
            return

        # ── Audio frames ─────────────────────────────────────────────────
        if isinstance(frame, AudioRawFrame) and direction == FrameDirection.DOWNSTREAM:
            audio_bytes = frame.audio

            # Phase 1: Enrollment
            if not self._enrollment_done:
                self._enrollment_buffer.extend(audio_bytes)

                if len(self._enrollment_buffer) >= self._enrollment_bytes_needed:
                    # Enroll in the background — don't block the pipeline
                    enrollment_audio = bytes(self._enrollment_buffer)
                    self._enrollment_buffer = bytearray()
                    self._enrollment_done = True

                    asyncio.create_task(
                        self._do_enrollment(enrollment_audio)
                    )

                # Always pass audio through during enrollment
                await self.push_frame(frame, direction)
                return

            # Phase 2: Verification
            if not self._segment_verified:
                # Accumulating audio for this segment's verification
                self._segment_buffer.extend(audio_bytes)

                if len(self._segment_buffer) >= self._segment_bytes_needed:
                    # Run verification
                    verification_audio = bytes(self._segment_buffer)
                    self._segment_buffer = bytearray()

                    is_match, score = await self._verifier.verify(
                        verification_audio, self._sample_rate
                    )
                    self._segment_verified = True
                    self._segment_is_match = is_match
                    self._segments_checked += 1

                    if is_match:
                        self._segments_passed += 1
                        logger.info(
                            "[SpeakerGate] ✅ Speaker MATCH | score={:.3f}",
                            score,
                        )
                    else:
                        self._segments_blocked += 1
                        logger.info(
                            "[SpeakerGate] ❌ Speaker MISMATCH | score={:.3f} — dropping audio",
                            score,
                        )

                # While accumulating, let audio through (optimistic).
                # If verification later fails, subsequent frames get dropped.
                await self.push_frame(frame, direction)
                return

            # Already verified for this segment
            if self._segment_is_match:
                await self.push_frame(frame, direction)
            # else: silently drop — not the enrolled speaker

        else:
            # Non-audio frames always pass through
            await self.push_frame(frame, direction)

    async def _do_enrollment(self, audio_bytes: bytes):
        """Enroll the speaker in the background."""
        success = await self._verifier.enroll(audio_bytes, self._sample_rate)
        if success:
            logger.info("[SpeakerGate] 🎤 Speaker enrollment complete")
        else:
            logger.warning(
                "[SpeakerGate] ⚠️ Enrollment failed — gate will remain open"
            )
