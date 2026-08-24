"""Groq LLM service with reasoning params routed through extra_body."""

from __future__ import annotations

from typing import Any

from pipecat.adapters.services.open_ai_adapter import OpenAILLMInvocationParams
from pipecat.services.groq.llm import GroqLLMService

from services.llm_retry import RetryingChatCompletionsMixin

_REASONING_KEYS = ("reasoning_format", "reasoning_effort", "include_reasoning")
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


def ensure_user_query(messages: list[Any] | None) -> list[Any]:
    """Some Groq reasoning models error if the request has no user message."""
    existing = list(messages or [])
    if any(_message_role(msg) == "user" and _message_has_text(msg) for msg in existing):
        return existing
    return existing + [{"role": "user", "content": _USER_QUERY_SEED}]


class GroqReasoningLLMService(RetryingChatCompletionsMixin, GroqLLMService):
    """Groq LLM that passes Groq-specific reasoning fields via extra_body."""

    def build_chat_completion_params(
        self, params_from_context: OpenAILLMInvocationParams
    ) -> dict:
        params = super().build_chat_completion_params(params_from_context)
        extra_body = dict(params.get("extra_body") or {})

        for key in _REASONING_KEYS:
            if key in params:
                extra_body[key] = params.pop(key)

        if extra_body:
            params["extra_body"] = extra_body

        params["messages"] = ensure_user_query(params.get("messages"))
        return params
