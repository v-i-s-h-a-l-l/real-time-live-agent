"""Failover ordering: Cerebras → Cerebras 2 → Groq, and fail-fast clients."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.failover_llm import FailoverLLMService  # noqa: E402


def _service(fallbacks):
    return FailoverLLMService(api_key="primary-key", fallbacks=fallbacks)


def test_second_cerebras_is_tried_before_groq():
    service = _service(
        [
            {
                "name": "Cerebras-2",
                "api_key": "k2",
                "base_url": "https://api.cerebras.ai/v1",
                "model": "gpt-oss-120b",
            },
            {
                "name": "Groq",
                "api_key": "gk",
                "base_url": "https://api.groq.com/openai/v1",
                "model": "openai/gpt-oss-120b",
            },
        ]
    )
    assert [f["name"] for f in service._fallbacks] == ["Cerebras-2", "Groq"]
    assert service._fallbacks[0]["model"] == "gpt-oss-120b"
    assert service._fallbacks[1]["model"] == "openai/gpt-oss-120b"


def test_every_client_fails_fast_so_failover_is_immediate():
    """SDK-level retry/backoff would spend seconds on a provider that said no."""
    service = _service(
        [
            {
                "name": "Cerebras-2",
                "api_key": "k2",
                "base_url": "https://api.cerebras.ai/v1",
                "model": "gpt-oss-120b",
            }
        ]
    )
    assert service._client.max_retries == 0
    for fallback in service._fallbacks:
        assert fallback["client"].max_retries == 0


def test_no_fallbacks_configured_is_still_valid():
    service = _service([])
    assert service._fallbacks == []
    assert service._client.max_retries == 0
