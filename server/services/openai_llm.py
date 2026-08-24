"""OpenAI LLM for Lumina — low-latency chat, no reasoning leak into TTS."""

from __future__ import annotations

from pipecat.adapters.services.open_ai_adapter import OpenAILLMInvocationParams
from pipecat.services.openai.llm import OpenAILLMService

from services.groq_llm import ensure_user_query
from services.llm_retry import RetryingChatCompletionsMixin


class OpenAILLMTutorService(RetryingChatCompletionsMixin, OpenAILLMService):
    """Official OpenAI chat completions for live tutoring."""

    def build_chat_completion_params(
        self, params_from_context: OpenAILLMInvocationParams
    ) -> dict:
        params = super().build_chat_completion_params(params_from_context)
        params["messages"] = ensure_user_query(params.get("messages"))
        # gpt-5.x / o-series: max_tokens is invalid; temperature is locked to default.
        params.pop("max_tokens", None)
        params.pop("temperature", None)
        return params
