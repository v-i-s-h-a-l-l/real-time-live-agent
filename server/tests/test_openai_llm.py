"""OpenAI tutor LLM: user-seed on empty turns."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.llm_retry import RetryingChatCompletionsMixin  # noqa: E402
from services.openai_llm import OpenAILLMTutorService  # noqa: E402


def test_openai_seeds_user_message_when_missing():
    llm = OpenAILLMTutorService(
        api_key="test-key",
        settings=OpenAILLMTutorService.Settings(model="gpt-5.6-luna"),
    )
    params = llm.build_chat_completion_params({"messages": []})
    assert any(
        msg.get("role") == "user" and msg.get("content")
        for msg in params["messages"]
    )
    assert "max_tokens" not in params
    assert "temperature" not in params


def test_openai_uses_max_completion_tokens():
    llm = OpenAILLMTutorService(
        api_key="test-key",
        settings=OpenAILLMTutorService.Settings(
            model="gpt-5.6-luna",
            max_completion_tokens=512,
        ),
    )
    params = llm.build_chat_completion_params({"messages": []})
    assert "max_tokens" not in params
    assert params.get("max_completion_tokens") == 512
    assert "temperature" not in params


def test_openai_keeps_existing_user_message():
    llm = OpenAILLMTutorService(
        api_key="test-key",
        settings=OpenAILLMTutorService.Settings(model="gpt-5.6-luna"),
    )
    params = llm.build_chat_completion_params(
        {"messages": [{"role": "user", "content": "Explain the lemma."}]}
    )
    user_msgs = [m for m in params["messages"] if m.get("role") == "user"]
    assert user_msgs == [{"role": "user", "content": "Explain the lemma."}]


def test_openai_tutor_retries_chat_completions():
    assert issubclass(OpenAILLMTutorService, RetryingChatCompletionsMixin)
