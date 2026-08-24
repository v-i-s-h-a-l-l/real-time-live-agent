"""OpenRouter LLM (OpenAI-compatible) with reasoning routed through extra_body."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pipecat.adapters.services.open_ai_adapter import OpenAILLMInvocationParams
from pipecat.services.openai.llm import OpenAILLMService

from services.groq_llm import ensure_user_query
from services.llm_retry import RetryingChatCompletionsMixin

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLMService(RetryingChatCompletionsMixin, OpenAILLMService):
    """OpenRouter chat completions. Reasoning stays in extra_body (SDK-safe)."""

    supports_developer_role = False

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = OPENROUTER_BASE_URL,
        default_headers: Mapping[str, str] | None = None,
        **kwargs,
    ):
        headers = {
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:3000"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Lumina"),
        }
        if default_headers:
            headers.update(default_headers)
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            default_headers=headers,
            **kwargs,
        )

    def build_chat_completion_params(
        self, params_from_context: OpenAILLMInvocationParams
    ) -> dict:
        params = super().build_chat_completion_params(params_from_context)
        extra_body = dict(params.get("extra_body") or {})

        if "reasoning" in params:
            extra_body["reasoning"] = params.pop("reasoning")

        if extra_body:
            params["extra_body"] = extra_body

        params["messages"] = ensure_user_query(params.get("messages"))
        return params
