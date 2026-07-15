"""
FailoverLLMService
──────────────────
An OpenAI-compatible LLM service that tries a primary provider first and, if that
call fails (e.g. Cerebras returns HTTP 429 "queue_exceeded" under load), transparently
retries the exact same request against one or more fallback providers.

Why this exists:
    A single provider can rate-limit you at the worst moment. Instead of surfacing an
    empty response (which the empty-guard turns into "sorry, what?"), we just send the
    same prompt to another provider that hosts the same model. The user never notices.

The same model (gpt-oss-120b) is hosted by both Cerebras and Groq, so failover keeps
responses consistent — only the endpoint changes.

Failover happens at request-creation time (where 429 / rate-limit / connection errors
are raised), before any tokens have streamed, so there is no partial/duplicated speech.
"""

from typing import List, Optional, TypedDict

from loguru import logger

from pipecat.services.cerebras.llm import CerebrasLLMService
from pipecat.services.settings import assert_given


class FallbackProvider(TypedDict):
    """Config for one fallback OpenAI-compatible provider."""

    name: str
    api_key: str
    base_url: str
    model: str


class FailoverLLMService(CerebrasLLMService):
    """Cerebras-primary LLM with automatic failover to other OpenAI-compatible providers.

    Args:
        api_key: Primary (Cerebras) API key.
        fallbacks: Ordered list of fallback providers. Tried in order when the
            primary — and each earlier fallback — fails. May be empty, in which
            case this behaves exactly like a plain CerebrasLLMService.
        settings: Standard CerebrasLLMService.Settings.
    """

    def __init__(
        self,
        *,
        api_key: str,
        fallbacks: Optional[List[FallbackProvider]] = None,
        settings=None,
        **kwargs,
    ):
        super().__init__(api_key=api_key, settings=settings, **kwargs)

        self._fallbacks = []
        for fb in fallbacks or []:
            client = self.create_client(api_key=fb["api_key"], base_url=fb["base_url"])
            self._fallbacks.append(
                {"name": fb["name"], "client": client, "model": fb["model"]}
            )

        if self._fallbacks:
            logger.info(
                "[FailoverLLM] {} fallback provider(s) ready: {}",
                len(self._fallbacks),
                ", ".join(f"{f['name']}({f['model']})" for f in self._fallbacks),
            )
        else:
            logger.info(
                "[FailoverLLM] no fallback providers configured — running primary only"
            )

    async def get_chat_completions(self, context):
        """Try the primary provider, then each fallback in order on failure."""
        adapter = self.get_llm_adapter()
        params_from_context = adapter.get_llm_invocation_params(
            context,
            system_instruction=assert_given(self._settings.system_instruction),
            convert_developer_to_user=not self.supports_developer_role,
        )
        params = self.build_chat_completion_params(params_from_context)

        # 1. Primary (Cerebras)
        try:
            return await self._client.chat.completions.create(**params)
        except Exception as primary_err:
            last_err = primary_err
            logger.warning(
                "[FailoverLLM] primary (Cerebras) failed: {} — trying fallbacks",
                primary_err,
            )

        # 2. Fallbacks, in order
        for fb in self._fallbacks:
            try:
                fb_params = dict(params)
                fb_params["model"] = fb["model"]
                logger.info(
                    "[FailoverLLM] retrying on fallback: {} ({})", fb["name"], fb["model"]
                )
                return await fb["client"].chat.completions.create(**fb_params)
            except Exception as fb_err:
                last_err = fb_err
                logger.warning(
                    "[FailoverLLM] fallback {} failed: {}", fb["name"], fb_err
                )

        # 3. Everything failed — raise the last error so the empty-guard can
        #    still inject a graceful fallback line.
        raise last_err
