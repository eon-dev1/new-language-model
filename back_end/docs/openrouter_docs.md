# OpenRouter API Reference

Technical details relevant to NLM's integration. Not a general OpenRouter guide — only what we need.

## Two Endpoints

OpenRouter exposes two API-compatible endpoints:

| Endpoint | Format | Base URL |
|----------|--------|----------|
| Anthropic-compatible | Anthropic Messages API | `https://openrouter.ai/api/v1/messages (SDK base_url: `https://openrouter.ai/api` — the SDK appends `/v1/messages`)` |
| OpenAI-compatible | OpenAI Chat Completions | `https://openrouter.ai/api/v1/chat/completions` |

Both accept the same `model` parameter (e.g. `anthropic/claude-sonnet-4.6`, `qwen/qwen3.5-397b-a17b`).

## Model IDs

OpenRouter uses **dot notation** for version numbers, not dashes:

| Model | OpenRouter ID | Direct Anthropic ID |
|-------|--------------|---------------------|
| Opus 4.6 | `anthropic/claude-opus-4.6` | `claude-opus-4-6` |
| Sonnet 4.6 | `anthropic/claude-sonnet-4.6` | `claude-sonnet-4-6` |
| Haiku 4.5 | `anthropic/claude-haiku-4.5` | `claude-haiku-4-5-20251001` |
| Qwen 3.5 397B | `qwen/qwen3.5-397b-a17b` | N/A |
| Qwen 3.5 35B | `qwen/qwen3.5-35b-a3b` | N/A |

## Thinking / Reasoning Support

### Anthropic models on OpenRouter

The Anthropic-compatible endpoint passes through the native `thinking` parameter and `anthropic-beta` headers for Claude models. Works the same as direct Anthropic API:

```python
thinking={"type": "enabled", "budget_tokens": 10000}
betas=["interleaved-thinking-2025-05-14"]
```

Claude 4.6 models also support `thinking: {"type": "adaptive"}` (model self-regulates thinking depth).

### Qwen models on OpenRouter

Qwen 3.5 has **native thinking** — trained with hybrid think/non-think mode. The model produces `<think>...</think>` blocks before its final answer. Both `qwen3.5-397b-a17b` and `qwen3.5-35b-a3b` have `supports_reasoning: true` on OpenRouter.

**Critical limitation:** Qwen thinking is only accessible via the **OpenAI-compatible endpoint** using the unified `reasoning` parameter:

```json
{
  "model": "qwen/qwen3.5-397b-a17b",
  "reasoning": {
    "effort": "high"
  }
}
```

The Anthropic SDK's `thinking` parameter sent through the Anthropic-compatible endpoint is **silently ignored** for Qwen models — not rejected, just dropped. This means:

- Anthropic SDK + OpenRouter + Qwen = chat works, but **no thinking**
- OpenAI SDK/httpx + OpenRouter + Qwen = chat works **with thinking**

### Unified `reasoning` parameter (OpenAI-compatible endpoint)

OpenRouter provides a cross-provider `reasoning` parameter on the OpenAI endpoint:

```json
{"reasoning": {"effort": "high"}}        // let OpenRouter decide budget
{"reasoning": {"max_tokens": 8000}}      // explicit budget
```

This works for both Anthropic and Qwen models on the OpenAI endpoint, but NLM currently uses the Anthropic SDK (Anthropic-compatible endpoint).

## Prompt Caching

OpenRouter supports Anthropic-style `cache_control` breakpoints for Anthropic models:

```python
system = [{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]
```

For non-Anthropic models (Qwen), `cache_control` fields should not be sent — they may be silently ignored or cause errors. OpenRouter handles caching implicitly at their proxy layer for many providers regardless of whether `cache_control` is present.

## Required Headers

```python
headers = {
    "Authorization": f"Bearer {api_key}",
    "HTTP-Referer": "https://nlm-bible-translation.app",
    "X-Title": "NLM Bible Translation",
}
```

Note: When using the Anthropic SDK with `base_url`, the SDK handles `Authorization` via the `api_key` parameter. The `HTTP-Referer` and `X-Title` headers are optional but recommended by OpenRouter for app identification and may be needed for rate limit considerations.

## Context Windows

| Model | Context | Max Output |
|-------|---------|------------|
| `anthropic/claude-opus-4.6` | 1,000,000 | — |
| `anthropic/claude-sonnet-4.6` | 1,000,000 | — |
| `anthropic/claude-haiku-4.5` | 200,000 | — |
| `qwen/qwen3.5-397b-a17b` | 262,144 | 65,536 |
| `qwen/qwen3.5-35b-a3b` | 262,144 | 65,536 |

## OpenAI-Compatible Endpoint — Streaming Format

Standard OpenAI SSE format: `data: {JSON}\n\n`, ending with `data: [DONE]\n\n`.

### Reasoning/Thinking in Streaming Responses

Reasoning content arrives in `choices[0].delta.reasoning_details` — a structured array, NOT in `<think>` tags within `content`:

```json
{
  "choices": [{
    "delta": {
      "reasoning_details": [{
        "type": "reasoning.text",
        "text": "partial reasoning chunk...",
        "id": "reasoning-text-1",
        "format": "anthropic-claude-v1",
        "index": 0
      }],
      "content": null
    }
  }]
}
```

Three `type` values for `reasoning_details` entries:
- `reasoning.text` — raw reasoning with `text` field (and optional `signature`)
- `reasoning.summary` — high-level overview with `summary` field
- `reasoning.encrypted` — opaque reasoning with `data` field (base64-encoded)

The top-level `reasoning` string on the message is a convenience flattening — `reasoning_details` is the canonical source.

Usage: `usage.completion_tokens_details.reasoning_tokens` for reasoning token counts.

### Tool Calls in Streaming

Standard OpenAI pattern — `choices[0].delta.tool_calls` arrives incrementally with `index` field for reconstruction. `finish_reason === "tool_calls"` signals execution needed.

**OpenRouter-specific**: The `tools` parameter must be included in **every request** in a multi-turn tool call sequence, not just the first.

### Reasoning + Tool Use Combined

Works — OpenRouter calls it "interleaved thinking." **Critical constraint**: when continuing after a tool call, you **must preserve the complete `reasoning_details` array** verbatim from the previous assistant turn. Models pause reasoning mid-construction to invoke tools and need the original context to resume.

### `reasoning` Parameter (Request)

```json
{
  "reasoning": {
    "effort": "high",          // xhigh|high|medium|low|minimal|none
    "max_tokens": 8000,        // alternative to effort (mutually exclusive)
    "exclude": false,          // suppress reasoning from response (still billed)
    "summary": "auto"          // auto|concise|detailed
  }
}
```

Constraints:
- `effort` and `max_tokens` are mutually exclusive
- For Anthropic models: min 1,024 tokens, max 128,000
- `include_reasoning` is legacy — use `reasoning` object instead

### OpenRouter-Specific SSE Details

- **Keepalive comments**: `": OPENROUTER PROCESSING"` sent before first token to prevent timeouts. Safe to ignore.
- `provider` field in chunk root — identifies upstream provider
- `native_finish_reason` — raw provider value before OpenRouter normalization
- **Mid-stream errors**: emitted as SSE event with `finish_reason: "error"` rather than dropped connection
- `X-Generation-Id` response header for querying generation stats

## Provider Routing

OpenRouter may route requests to different backends (direct Anthropic, Bedrock, Vertex, Azure) depending on availability. To pin to a specific provider:

```json
{"provider": {"order": ["Anthropic"]}}
```

This may be relevant if thinking or caching behavior varies across backends.

## Rate Limiting

- Limits are **model-specific** and **per-account** (not per API key)
- HTTP `429` when rate limited, `402` when credits exhausted
- Free model variants (`:free` suffix) have lower limits
- No difference in rate limiting between the two endpoints
