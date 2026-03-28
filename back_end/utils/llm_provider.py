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
from typing import Any, AsyncGenerator

import anthropic

from shared.chat_config import load_config

logger = logging.getLogger(__name__)

THINKING_BUDGET_TOKENS = 8000
THINKING_MAX_TOKENS = 16192  # budget + generous output headroom
HAIKU_MODELS = {"claude-haiku-4-5-20251001"}
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

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)
        self.model = model
        self.is_local = base_url is not None  # Local LLMs never support thinking

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

        # Inject thinking — guard on local provider AND Haiku model
        use_beta = thinking_enabled and not self.is_local and self.model not in HAIKU_MODELS
        if use_beta:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}
            kwargs["betas"] = [THINKING_BETA_HEADER]
            kwargs["max_tokens"] = max(max_tokens, THINKING_MAX_TOKENS)

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
                    yield {
                        "type": "usage",
                        "input_tokens": final.usage.input_tokens,
                        "output_tokens": final.usage.output_tokens,
                    }

            yield {"type": "done"}

        except anthropic.APIConnectionError as e:
            logger.error(f"Cannot connect to LLM: {e}")
            yield {"type": "error", "content": f"Cannot connect to LLM server. Is it running? ({e})"}
        except anthropic.APIError as e:
            logger.error(f"LLM API error: {e}")
            yield {"type": "error", "content": f"LLM API error: {e.message}"}
        except Exception as e:
            logger.error(f"Unexpected error in LLM provider: {e}")
            yield {"type": "error", "content": str(e)}


def get_provider() -> LLMProvider:
    """
    Create an LLM provider from current config.

    Both Anthropic and local use the same AnthropicProvider class,
    just with different base_url and api_key settings.

    Raises:
        ValueError: If config is invalid (e.g., no API key for Anthropic).
    """
    config = load_config()
    provider_type = config.get("llm_provider", "anthropic")

    if provider_type == "anthropic":
        api_key = config.get("anthropic_api_key", "")
        if not api_key:
            raise ValueError("Anthropic API key not configured. Set it in Chat Settings.")
        model = config.get("anthropic_model", "claude-sonnet-4-6")
        return AnthropicProvider(api_key=api_key, model=model)

    elif provider_type == "local":
        base_url = config.get("local_base_url", "http://127.0.0.1:8080")
        model = config.get("local_model", "default")
        # Local servers don't need a real API key but the SDK requires one
        return AnthropicProvider(api_key="local", model=model, base_url=base_url)

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")
