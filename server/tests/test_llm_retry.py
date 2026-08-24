"""LLM retry/backoff: 429/5xx/timeout, short delays, ops_event."""

from __future__ import annotations

import asyncio
import sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

from services.llm_retry import (  # noqa: E402
    backoff_secs,
    is_retryable,
    with_retries,
)


class _RateLimit(Exception):
    status_code = 429


class _ServerError(Exception):
    status_code = 503


class _BadRequest(Exception):
    status_code = 400


def test_backoff_stays_subsecond():
    assert backoff_secs(1) == 0.2
    assert backoff_secs(2) == 0.4
    assert backoff_secs(3) == 0.8
    assert backoff_secs(8) == 0.8


def test_429_and_5xx_are_retryable_400_is_not():
    assert is_retryable(_RateLimit("rate limited"))
    assert is_retryable(_ServerError("unavailable"))
    assert is_retryable(TimeoutError("timed out"))
    assert not is_retryable(_BadRequest("bad json"))
    assert not is_retryable(asyncio.CancelledError())


def test_retry_succeeds_on_second_attempt(monkeypatch):
    async def _instant(_delay=0, *_a, **_k):
        return None

    monkeypatch.setattr("services.llm_retry.asyncio.sleep", _instant)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _RateLimit("429")
        return "ok"

    async def run():
        return await with_retries(flaky, op="chat_completions", category="llm")

    assert asyncio.run(run()) == "ok"
    assert calls["n"] == 2


def test_retry_emits_ops_event_then_exhausts(monkeypatch):
    async def _instant(_delay=0, *_a, **_k):
        return None

    monkeypatch.setattr("services.llm_retry.asyncio.sleep", _instant)
    buf = StringIO()
    sink_id = logger.add(buf, format="{message}")

    async def always_429():
        raise _RateLimit("rate limited")

    async def run():
        try:
            await with_retries(always_429, op="chat_completions", category="llm")
        except _RateLimit:
            return

    try:
        asyncio.run(run())
        text = buf.getvalue()
        assert "llm_retry" in text
        assert "llm_retry_exhausted" in text
        assert "api_key" not in text.lower()
    finally:
        logger.remove(sink_id)


def test_non_retryable_does_not_emit_exhausted(monkeypatch):
    async def _instant(_delay=0, *_a, **_k):
        return None

    monkeypatch.setattr("services.llm_retry.asyncio.sleep", _instant)
    buf = StringIO()
    sink_id = logger.add(buf, format="{message}")

    async def bad():
        raise _BadRequest("nope")

    async def run():
        try:
            await with_retries(bad, op="chat_completions", category="llm")
        except _BadRequest:
            return

    try:
        asyncio.run(run())
        text = buf.getvalue()
        assert "llm_retry" not in text
        assert "llm_retry_exhausted" not in text
    finally:
        logger.remove(sink_id)
