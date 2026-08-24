"""OpenRouter LLM wiring: reasoning in extra_body, user-seed on empty turns."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.llm_retry import RetryingChatCompletionsMixin  # noqa: E402
from services.openrouter_llm import (  # noqa: E402
    OPENROUTER_BASE_URL,
    OpenRouterLLMService,
)


def test_openrouter_routes_reasoning_via_extra_body():
    llm = OpenRouterLLMService(
        api_key="test-key",
        settings=OpenRouterLLMService.Settings(
            model="google/gemma-4-26b-a4b-it:free",
            extra={"reasoning": {"enabled": True}},
        ),
    )
    params = llm.build_chat_completion_params({"messages": []})
    assert params["extra_body"]["reasoning"] == {"enabled": True}
    assert "reasoning" not in params
    assert any(
        msg.get("role") == "user" and msg.get("content")
        for msg in params["messages"]
    )


def test_openrouter_keeps_existing_user_message():
    llm = OpenRouterLLMService(
        api_key="test-key",
        settings=OpenRouterLLMService.Settings(
            model="google/gemma-4-26b-a4b-it:free"
        ),
    )
    params = llm.build_chat_completion_params(
        {"messages": [{"role": "user", "content": "Explain the lemma."}]}
    )
    user_msgs = [m for m in params["messages"] if m.get("role") == "user"]
    assert user_msgs == [{"role": "user", "content": "Explain the lemma."}]


def test_openrouter_base_url():
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"


def test_openrouter_retries_chat_completions():
    assert issubclass(OpenRouterLLMService, RetryingChatCompletionsMixin)
