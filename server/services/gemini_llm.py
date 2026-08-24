"""Google Gemini LLM service wrapper for Lumina.

Wraps ``pipecat.services.google.llm.GoogleLLMService`` with the same guardrails
the Groq wrapper applies: guarantees at least one user message on the request
(so the opening turn does not fail on system-only context) and lets us keep the
service construction in one place.
"""

from __future__ import annotations

from typing import Any

from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.google.llm import GoogleLLMService

from services.llm_retry import notify_llm_retry, with_retries

_USER_QUERY_SEED = "Hi"


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or "")
    return str(getattr(message, "role", "") or "")


def _message_has_text(message: Any) -> bool:
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(
            isinstance(part, dict) and str(part.get("text") or "").strip()
            for part in content
        )
    return bool(content)


class GeminiTutorLLMService(GoogleLLMService):
    """Google Gemini LLM with a user-seed guarantee on the opening turn."""

    async def _process_context(self, context: LLMContext, *args, **kwargs):
        messages = context.get_messages() if context is not None else []
        if not any(
            _message_role(msg) == "user" and _message_has_text(msg)
            for msg in messages
        ):
            context.add_message({"role": "user", "content": _USER_QUERY_SEED})
        return await super()._process_context(context, *args, **kwargs)

    async def _stream_content(self, context: LLMContext, *args, **kwargs):
        parent = super()._stream_content

        async def _once():
            return await parent(context, *args, **kwargs)

        async def _on_retry(attempt: int, exc: BaseException, _delay: float) -> None:
            await notify_llm_retry(self, attempt=attempt, exc=exc, op="gemini_stream")

        return await with_retries(
            _once,
            op="gemini_stream",
            category="llm",
            on_retry=_on_retry,
        )
