"""
LLM Provider abstraction layer.

Supports:
- Anthropic API (Claude models) via anthropic SDK
- Local LLMs (llama.cpp, Ollama) via anthropic SDK pointed at local base URL

Both use the Anthropic Messages API format. llama.cpp supports
/v1/messages natively since Nov 2025, so we use the same SDK for both.
The only difference is base_url and api_key.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Literal

import anthropic

from shared import model_registry
from shared.chat_config import load_config
from shared.model_registry import get_api_format

logger = logging.getLogger(__name__)

THINKING_BUDGET_TOKENS = 8000
THINKING_MAX_TOKENS = 16192  # budget + generous output headroom
THINKING_BETA_HEADER = "interleaved-thinking-2025-05-14"


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        thinking_enabled: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream a chat completion.

        Yields events:
          {"type": "text", "content": "..."}        - text chunk
          {"type": "tool_use", "id": "...", "name": "...", "input": {...}}  - tool call request
          {"type": "done"}                           - stream complete
          {"type": "error", "content": "..."}        - error occurred
        """
        raise NotImplementedError  # pragma: no cover


class AnthropicProvider(LLMProvider):
    """
    Anthropic Messages API provider.

    Works with both the real Anthropic API and local servers that
    implement the Anthropic /v1/messages endpoint (e.g., llama.cpp).
    """

    def __init__(self, api_key: str, model: str, base_url: str | None = None,
                 provider_type: Literal["local", "openrouter"] = "openrouter"):
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)
        self.model = model
        self.provider_type = provider_type

    def _apply_prompt_caching(self, kwargs: dict[str, Any]) -> None:
        """Add cache_control breakpoints to system prompt and last tool definition.

        Converts system string → content block list (required by Anthropic caching API).
        Shallow-copies the last tool dict before mutating to avoid polluting shared registries.
        """
        if "system" in kwargs and isinstance(kwargs["system"], str):
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": kwargs["system"],
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        if "tools" in kwargs and kwargs["tools"]:
            tools = list(kwargs["tools"])
            last_tool = dict(tools[-1])
            last_tool["cache_control"] = {"type": "ephemeral"}
            tools[-1] = last_tool
            kwargs["tools"] = tools

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        thinking_enabled: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        # Inject thinking — guard on global config flag, provider_type, and per-model registry check.
        # load_config() here is the authoritative enforcement point: impossible to bypass via any
        # frontend or API path. Intentional sync I/O — small JSON file, runs once per stream call.
        global_thinking_enabled = load_config().get("thinking_enabled", True)
        use_beta = (
            thinking_enabled
            and global_thinking_enabled
            and model_registry.supports_thinking(self.model)
            and self.provider_type != "local"
        )
        if use_beta:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}
            kwargs["betas"] = [THINKING_BETA_HEADER]
            kwargs["max_tokens"] = max(max_tokens, THINKING_MAX_TOKENS)
            if self.provider_type == "openrouter":
                # OpenRouter requires the beta header as an explicit HTTP header;
                # the SDK's `betas=` parameter alone is not forwarded to Anthropic.
                kwargs["extra_headers"] = {"x-anthropic-beta": THINKING_BETA_HEADER}

        if self.provider_type != "local" and not self.model.startswith("qwen/"):
            self._apply_prompt_caching(kwargs)

        if self.provider_type == "openrouter":
            logger.info(f"[openrouter] stream_chat model={self.model} tools={len(kwargs.get('tools', []))} thinking={use_beta}")

        try:
            # Beta endpoint required when betas header is present (e.g. interleaved-thinking)
            stream_method = self.client.beta.messages.stream if use_beta else self.client.messages.stream
            async with stream_method(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield {"type": "text", "content": event.delta.text}
                        elif hasattr(event.delta, "partial_json"):
                            yield {"type": "tool_input_delta", "content": event.delta.partial_json}
                        elif event.delta.type == "thinking_delta":
                            yield {"type": "thinking_delta", "content": event.delta.thinking}
                    elif event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            yield {
                                "type": "tool_use_start",
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                            }

                # Check final message for tool_use and thinking blocks
                final = await stream.get_final_message()
                for block in final.content:
                    if block.type == "tool_use":
                        yield {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    elif block.type == "thinking":
                        # Internal event: used by _run_tool_loop for API continuity + DB persistence
                        # Never forwarded to frontend SSE stream
                        yield {
                            "type": "thinking_block",
                            "thinking": block.thinking,
                            "signature": block.signature,
                        }

                # Yield usage data if available and non-zero
                if (
                    hasattr(final, "usage")
                    and final.usage
                    and getattr(final.usage, "input_tokens", 0)
                ):
                    cache_creation = getattr(final.usage, "cache_creation_input_tokens", None) or 0
                    cache_read = getattr(final.usage, "cache_read_input_tokens", None) or 0
                    logger.info(f"[cache] usage: input={final.usage.input_tokens} creation={cache_creation} read={cache_read}")
                    if cache_read > 0:
                        logger.info(f"[cache] HIT: {cache_read} tokens read from cache")
                    elif cache_creation > 0:
                        logger.info(f"[cache] MISS: {cache_creation} tokens written to cache")
                    yield {
                        "type": "usage",
                        "input_tokens": final.usage.input_tokens,
                        "output_tokens": final.usage.output_tokens,
                        "cache_creation_input_tokens": cache_creation,
                        "cache_read_input_tokens": cache_read,
                    }

            yield {"type": "done"}

        except anthropic.APIConnectionError as e:
            if self.provider_type == "openrouter":
                logger.error(f"[openrouter] Cannot connect: {e}")
            else:
                logger.error(f"Cannot connect to LLM: {e}")
            yield {"type": "error", "content": "Cannot connect to LLM server. Is it running?"}
        except anthropic.APIError as e:
            if self.provider_type == "openrouter":
                logger.error(f"[openrouter] API error model={self.model}: {e}")
            else:
                logger.error(f"LLM API error: {e}")
            yield {"type": "error", "content": f"LLM API error: {e.message}"}
        except Exception:
            if self.provider_type == "openrouter":
                logger.exception(f"[openrouter] Unexpected error model={self.model}")
            else:
                logger.exception("Unexpected error in LLM provider")
            yield {"type": "error", "content": "Server error"}


class ProviderConfigError(ValueError):
    """Raised by get_provider() for user-actionable LLM configuration problems.

    A distinct type so route handlers can surface these messages to the user
    verbatim without also catching unrelated ValueErrors. Notably, pydantic's
    ValidationError is a ValueError subclass, and MongoDBSettings validation
    failures stringify the rejected connection URI — username in full, password
    at least in part.
    Subclasses ValueError so existing callers and tests keep working.
    """


def get_provider() -> LLMProvider:
    """
    Create an LLM provider from current config.

    Both Anthropic and local use the same AnthropicProvider class,
    just with different base_url and api_key settings.

    Raises:
        ProviderConfigError: If config is invalid (e.g., no API key configured).
            A ValueError subclass, deliberately distinct so callers can surface
            these messages verbatim without also catching unrelated ValueErrors —
            notably pydantic ValidationError, which stringifies rejected input.
    """
    config = load_config()
    provider_type = config.get("llm_provider", "openrouter")

    if provider_type == "openrouter":
        api_key = config.get("openrouter_api_key", "")
        if not api_key:
            raise ProviderConfigError("OpenRouter API key not configured. Set it in Chat Settings.")
        model = config.get("openrouter_model", "anthropic/claude-sonnet-4.6")

        if get_api_format(model) == "openai":
            from utils.openai_provider import OpenAIProvider
            return OpenAIProvider(api_key=api_key, model=model)
        else:
            return AnthropicProvider(
                api_key=api_key, model=model,
                base_url="https://openrouter.ai/api",
                provider_type="openrouter",
            )

    elif provider_type == "local":
        base_url = config.get("local_base_url", "http://127.0.0.1:8080")
        model = config.get("local_model", "default")
        # Local servers don't need a real API key but the SDK requires one
        return AnthropicProvider(api_key="local", model=model, base_url=base_url, provider_type="local")

    else:
        raise ProviderConfigError(f"Unknown LLM provider: {provider_type}")
