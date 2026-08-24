"""Single-provider Groq LLM wiring."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from services.groq_llm import GroqReasoningLLMService  # noqa: E402
from services.llm_retry import RetryingChatCompletionsMixin  # noqa: E402


def test_groq_llm_routes_reasoning_params_via_extra_body():
    llm = GroqReasoningLLMService(
        api_key="test-key",
        settings=GroqReasoningLLMService.Settings(
            model=config.LLM_MODEL,
            extra={
                "reasoning_effort": "low",
                "include_reasoning": False,
            },
        ),
    )
    params = llm.build_chat_completion_params({"messages": []})
    assert params["extra_body"]["reasoning_effort"] == "low"
    assert params["extra_body"]["include_reasoning"] is False
    assert "reasoning_effort" not in params
    assert "include_reasoning" not in params
    assert any(
        msg.get("role") == "user" and msg.get("content")
        for msg in params["messages"]
    )


def test_groq_keeps_existing_user_message():
    llm = GroqReasoningLLMService(
        api_key="test-key",
        settings=GroqReasoningLLMService.Settings(model=config.LLM_MODEL),
    )
    params = llm.build_chat_completion_params(
        {"messages": [{"role": "user", "content": "Explain the lemma."}]}
    )
    user_msgs = [m for m in params["messages"] if m.get("role") == "user"]
    assert user_msgs == [{"role": "user", "content": "Explain the lemma."}]


def test_groq_default_model_is_gpt_oss():
    assert config._LLM_DEFAULTS["groq"] == "openai/gpt-oss-120b"


def test_groq_retries_chat_completions():
    assert issubclass(GroqReasoningLLMService, RetryingChatCompletionsMixin)
