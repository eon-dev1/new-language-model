"""
Model registry — single source of truth for backend model metadata.

Context windows, thinking support flags, and display names live here.
Backend modules (llm_provider, llm_tool_loop) import from this registry
instead of maintaining scattered constants.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ModelInfo:
    id: str                    # API model ID (e.g. "claude-sonnet-4-6")
    label: str                 # Display name (e.g. "Sonnet 4.6")
    context_window: int        # Max input tokens
    supports_thinking: bool    # Whether extended thinking is available
    provider: str              # "anthropic" or "openrouter"
    api_format: Literal["anthropic", "openai"] = "anthropic"  # Wire format for provider routing


# Direct Anthropic models
ANTHROPIC_MODELS: dict[str, ModelInfo] = {
    "claude-opus-4-6": ModelInfo(
        id="claude-opus-4-6", label="Opus 4.6",
        context_window=1_000_000, supports_thinking=True, provider="anthropic",
    ),
    "claude-sonnet-4-6": ModelInfo(
        id="claude-sonnet-4-6", label="Sonnet 4.6",
        context_window=1_000_000, supports_thinking=True, provider="anthropic",
    ),
    "claude-haiku-4-5-20251001": ModelInfo(
        id="claude-haiku-4-5-20251001", label="Haiku 4.5",
        context_window=200_000, supports_thinking=False, provider="anthropic",
    ),
}

# OpenRouter models (note: dot notation in IDs, e.g. "4.6" not "4-6")
OPENROUTER_MODELS: dict[str, ModelInfo] = {
    "anthropic/claude-opus-4.6": ModelInfo(
        id="anthropic/claude-opus-4.6", label="Opus 4.6",
        context_window=1_000_000, supports_thinking=True, provider="openrouter",
    ),
    "anthropic/claude-sonnet-4.6": ModelInfo(
        id="anthropic/claude-sonnet-4.6", label="Sonnet 4.6",
        context_window=1_000_000, supports_thinking=True, provider="openrouter",
    ),
    "anthropic/claude-haiku-4.5": ModelInfo(
        id="anthropic/claude-haiku-4.5", label="Haiku 4.5",
        context_window=200_000, supports_thinking=False, provider="openrouter",
    ),
    "qwen/qwen3.5-397b-a17b": ModelInfo(
        id="qwen/qwen3.5-397b-a17b", label="Qwen 3.5 397B",
        context_window=262_144, supports_thinking=False, provider="openrouter",
        api_format="openai",
    ),
    "qwen/qwen3.5-35b-a3b": ModelInfo(
        id="qwen/qwen3.5-35b-a3b", label="Qwen 3.5 35B",
        context_window=262_144, supports_thinking=False, provider="openrouter",
        api_format="openai",
    ),
}

ALL_MODELS: dict[str, ModelInfo] = {**ANTHROPIC_MODELS, **OPENROUTER_MODELS}

DEFAULT_CONTEXT_WINDOW = 200_000


def get_context_window(model_id: str) -> int:
    """Get context window for a model, falling back to default."""
    info = ALL_MODELS.get(model_id)
    return info.context_window if info else DEFAULT_CONTEXT_WINDOW


def supports_thinking(model_id: str) -> bool:
    """Check if a model supports extended thinking."""
    info = ALL_MODELS.get(model_id)
    return info.supports_thinking if info else False


def get_api_format(model_id: str) -> str:
    """Return wire format for a model. Used for provider routing."""
    info = ALL_MODELS.get(model_id)
    return info.api_format if info else "anthropic"
