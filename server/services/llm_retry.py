"""Short exponential retry for live-call LLM requests.

Voice latency budget is tight: 2–3 attempts, sub-second backoff. The empty
guard stays the last-resort filler and only fires after these retries are
done (it resets its timer on ``LLMRetryInProgressFrame``).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pipecat.frames.frames import SystemFrame

from ops_log import ops_event

T = TypeVar("T")

LLM_RETRY_ATTEMPTS = 3
LLM_RETRY_BASE_SECS = 0.2
LLM_RETRY_MAX_SECS = 0.8

RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

_TIMEOUT_NAMES = frozenset(
    {
        "TimeoutError",
        "APITimeoutError",
        "TimeoutException",
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "DeadlineExceeded",
        "ConnectError",
        "RemoteProtocolError",
    }
)

OnRetry = Callable[[int, BaseException, float], Awaitable[None]]


@dataclass
class LLMRetryInProgressFrame(SystemFrame):
    """Emitted before a retry so the empty guard does not fill in early."""

    attempt: int = 0
    status: int | None = None
    op: str | None = None


def backoff_secs(failed_attempt: int) -> float:
    """Delay after ``failed_attempt`` (1-based) before the next try."""
    delay = LLM_RETRY_BASE_SECS * (2 ** max(failed_attempt - 1, 0))
    return min(delay, LLM_RETRY_MAX_SECS)


def status_from_exc(exc: BaseException) -> int | None:
    for attr in ("status_code", "status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int) and code > 0:
            return code
    return None


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, asyncio.CancelledError):
        return False
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True
    if type(exc).__name__ in _TIMEOUT_NAMES:
        return True
    code = status_from_exc(exc)
    if code in RETRYABLE_STATUS:
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


async def notify_llm_retry(service: Any, *, attempt: int, exc: BaseException, op: str) -> None:
    """Push a retry signal so LLMEmptyGuardProcessor holds its filler."""
    push = getattr(service, "push_frame", None)
    if push is None:
        return
    try:
        await push(
            LLMRetryInProgressFrame(
                attempt=attempt,
                status=status_from_exc(exc),
                op=op,
            )
        )
    except Exception:
        return


async def with_retries(
    fn: Callable[[], Awaitable[T]],
    *,
    op: str,
    category: str = "llm",
    max_attempts: int = LLM_RETRY_ATTEMPTS,
    on_retry: OnRetry | None = None,
) -> T:
    """Run ``fn`` up to ``max_attempts`` times on 429/5xx/timeout."""
    last_exc: BaseException | None = None
    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            if not is_retryable(exc) or attempt >= attempts:
                if is_retryable(exc):
                    ops_event(
                        "llm_retry_exhausted",
                        category=category,
                        op=op,
                        attempt=attempt,
                        status=status_from_exc(exc),
                        error_type=type(exc).__name__,
                    )
                raise
            delay = backoff_secs(attempt)
            ops_event(
                "llm_retry",
                category=category,
                op=op,
                attempt=attempt,
                next_delay_ms=int(delay * 1000),
                status=status_from_exc(exc),
                error_type=type(exc).__name__,
            )
            if on_retry is not None:
                await on_retry(attempt, exc, delay)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


class RetryingChatCompletionsMixin:
    """Retry OpenAI-compatible ``get_chat_completions`` on 429/5xx/timeout."""

    async def get_chat_completions(self, context):
        parent = super().get_chat_completions

        async def _once():
            return await parent(context)

        async def _on_retry(attempt: int, exc: BaseException, _delay: float) -> None:
            await notify_llm_retry(self, attempt=attempt, exc=exc, op="chat_completions")

        return await with_retries(
            _once,
            op="chat_completions",
            category="llm",
            on_retry=_on_retry,
        )
