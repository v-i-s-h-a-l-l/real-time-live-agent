"""Cartesia TTS with a secondary provider or text-only degrade on billing errors.

Cartesia HTTP 402 (payment/quota) used to yield silence. This wrapper stays in
the same pipeline slot and, on a hard provider failure:

1. Switches to a configured fallback TTS (``TTS_FALLBACK_PROVIDER=openai``), or
2. Marks subsequent LLM text ``skip_tts`` so the transcript still reaches RTVI.
"""

from __future__ import annotations

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    StartFrame,
    TextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.tts_service import TTSService

from config import OPENAI_API_KEY, SAMPLE_RATE, TTS_FALLBACK_PROVIDER
from ops_log import ops_event

_BILLING_MARKERS = (
    "402",
    "payment required",
    "payment_required",
    "insufficient funds",
    "insufficient_quota",
    "quota exceeded",
    "out of credits",
    "credit exhausted",
    "billing",
)


def is_tts_hard_failure(error_msg: str) -> bool:
    text = (error_msg or "").lower()
    return any(marker in text for marker in _BILLING_MARKERS)


def compact_tts_reason(error_msg: str) -> str:
    text = (error_msg or "").lower()
    if "402" in text:
        return "http_402"
    if "quota" in text:
        return "quota"
    if "payment" in text or "billing" in text:
        return "billing"
    if "credit" in text:
        return "credits"
    return "provider_error"


class TTSFailoverController:
    """Pure failover state. ``primary`` → ``fallback`` or ``text``."""

    def __init__(self, *, has_fallback: bool) -> None:
        self.has_fallback = has_fallback
        self.mode = "primary"

    def consider(self, error_msg: str) -> str | None:
        if self.mode != "primary":
            return None
        if not is_tts_hard_failure(error_msg):
            return None
        self.mode = "fallback" if self.has_fallback else "text"
        return self.mode


def build_fallback_tts(*, sample_rate: int = SAMPLE_RATE) -> TTSService | None:
    """Secondary TTS if configured and keyed; otherwise None (text-only degrade)."""
    provider = (TTS_FALLBACK_PROVIDER or "").strip().lower()
    if provider == "openai":
        if not OPENAI_API_KEY:
            logger.warning(
                "TTS_FALLBACK_PROVIDER=openai but OPENAI_API_KEY is unset — "
                "Cartesia failures will degrade to text-only"
            )
            return None
        from pipecat.services.openai.tts import OpenAITTSService

        return OpenAITTSService(api_key=OPENAI_API_KEY, sample_rate=sample_rate)
    if provider:
        logger.warning(
            "Unknown TTS_FALLBACK_PROVIDER={} — Cartesia failures will degrade to text-only",
            provider,
        )
    return None


def apply_text_only_skip(frame: Frame) -> None:
    """Keep transcript flowing when Cartesia cannot speak."""
    if isinstance(frame, (TextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame)):
        frame.skip_tts = True


class CartesiaTTSWithFailover(CartesiaTTSService):
    """Cartesia in the TTS pipeline slot, with fallback or text-only on 402."""

    def __init__(
        self,
        *args,
        fallback: TTSService | None = None,
        session_id: str = "-",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._fallback = fallback
        self._session_id = session_id
        self._controller = TTSFailoverController(has_fallback=fallback is not None)

    def link(self, processor):
        super().link(processor)
        if self._fallback is not None:
            self._fallback._next = processor

    async def setup(self, setup):
        await super().setup(setup)
        if self._fallback is not None:
            await self._fallback.setup(setup)

    async def cleanup(self):
        if self._fallback is not None:
            await self._fallback.cleanup()
        await super().cleanup()

    def _trip_if_needed(self, error_msg: str) -> str | None:
        dest = self._controller.consider(error_msg)
        if not dest:
            return None
        ops_event(
            "tts_fallback",
            category="tts",
            session_id=self._session_id,
            to=dest,
            reason=compact_tts_reason(error_msg),
        )
        logger.warning(
            "[TTS_FAILOVER] Cartesia failed — switching to {} | session={} reason={}",
            dest,
            self._session_id,
            compact_tts_reason(error_msg),
        )
        return dest

    async def push_error(
        self,
        error_msg: str,
        exception: Exception | None = None,
        fatal: bool = False,
    ):
        self._trip_if_needed(error_msg)
        await super().push_error(error_msg, exception=exception, fatal=fatal)

    async def run_tts(self, text: str, context_id: str):
        if self._controller.mode == "fallback" and self._fallback is not None:
            async for frame in self._fallback.run_tts(text, context_id):
                yield frame
            return
        if self._controller.mode == "text":
            return

        async for frame in super().run_tts(text, context_id):
            if isinstance(frame, ErrorFrame) and self._trip_if_needed(frame.error or ""):
                if self._controller.mode == "fallback" and self._fallback is not None:
                    async for fallback_frame in self._fallback.run_tts(text, context_id):
                        yield fallback_frame
                    return
                return
            yield frame

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, (StartFrame, EndFrame, CancelFrame)):
            await super().process_frame(frame, direction)
            if self._fallback is not None:
                try:
                    if isinstance(frame, StartFrame):
                        await self._fallback.start(frame)
                    elif isinstance(frame, EndFrame):
                        await self._fallback.stop(frame)
                    else:
                        await self._fallback.cancel(frame)
                except Exception as exc:
                    logger.warning(
                        "[TTS_FAILOVER] fallback lifecycle failed | session={} err={}",
                        self._session_id,
                        type(exc).__name__,
                    )
            return

        if self._controller.mode == "text":
            apply_text_only_skip(frame)
            await super().process_frame(frame, direction)
            return

        if self._controller.mode == "fallback" and self._fallback is not None:
            await self._fallback.process_frame(frame, direction)
            return

        await super().process_frame(frame, direction)
