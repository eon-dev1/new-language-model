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

The Anthropic-compatible endpoint passes through the native `thinking` parameter for Claude models:

```python
thinking={"type": "enabled", "budget_tokens": 10000}
```

Claude 4.6 models also support `thinking: {"type": "adaptive"}` (model self-regulates thinking depth).

#### ✅ Beta header name: `x-anthropic-beta`, NOT `anthropic-beta` (VERIFIED live, 2026-06-07)

OpenRouter's documented mechanism for Claude beta features is the **`x-anthropic-beta`** header (note the `x-` prefix), per [Provider Routing → Anthropic Beta Features](https://openrouter.ai/docs/guides/routing/provider-selection). Supported values:

| Feature | Header value |
|---------|--------------|
| Interleaved Thinking | `interleaved-thinking-2025-05-14` |
| Fine-Grained Tool Streaming | `fine-grained-tool-streaming-2025-05-14` |
| Structured Outputs (strict tool use) | `structured-outputs-2025-11-13` |

The Anthropic SDK's `betas=[...]` argument emits the header as bare **`anthropic-beta`** (no `x-` prefix). [OpenRouterTeam/ai-sdk-provider#111](https://github.com/OpenRouterTeam/ai-sdk-provider/issues/111) reports OpenRouter's gateway does **not** forward the bare `anthropic-beta` header downstream to Anthropic (OpenRouter replied it was "tracked internally," Jul 2025 — may be fixed since).

**Confirmed by live test (2026-06-07).** A 2-turn tool loop through OpenRouter (`anthropic/claude-sonnet-4.6`) showed: with `betas=` only (the bare `anthropic-beta` header), the model thinks on turn 1 but **not** after a tool result — interleaved thinking is silently inactive. Adding `extra_headers={"x-anthropic-beta": "interleaved-thinking-2025-05-14"}` restores thinking after tool results. The bare header is **ignored, not rejected**, so sending both is safe. Thinking-block signatures round-trip without error in all cases.

**Fix for NLM:** on the OpenRouter path in `llm_provider.py`, send `extra_headers={"x-anthropic-beta": "interleaved-thinking-2025-05-14"}` (keep or drop the existing `betas=` — it's a harmless no-op over OpenRouter). Basic `thinking` works without the header; only *interleaving across tool calls* depends on it.

Note: `OpenRouter manages prompt caching and extended context automatically based on model capabilities` — those do not require a beta header. Only interleaved-thinking / fine-grained-streaming / structured-outputs need the explicit `x-anthropic-beta` header.

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

OpenRouter supports Anthropic-style `cache_control` breakpoints for Anthropic models. For Claude, caching is **never automatic** — you must place breakpoints yourself.

```python
system = [{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]
```

Two modes:
- **Automatic** — a single top-level `cache_control` that OpenRouter advances forward as the conversation grows. **Only works when routed to Anthropic-direct** — Bedrock and Vertex don't support top-level `cache_control` (OpenRouter will exclude them from routing if it's present).
- **Explicit per-block** — `cache_control` on individual content blocks. **Works across all Anthropic backends** (Anthropic, Bedrock, Vertex). **Limit: 4 breakpoints per request.**

**NLM uses explicit per-block** (`_apply_prompt_caching`: system block + last tool = 2 breakpoints). Consequence: caching survives regardless of which backend OpenRouter selects, so pinning `provider.order` is **not** required for caching to work.

**TTL:** default is 5-minute ephemeral. A 1-hour TTL is available for explicit breakpoints across all Claude backends and may help long batch-translation sessions:
```python
{"type": "ephemeral", "ttl": "1h"}   # cache write costs 2x base vs 1.25x for 5-min
```

**Billing / metrics:** cache writes ≈ 1.25x base input (5-min TTL); cache reads ≈ 0.1x base input. Surfaced as `cache_creation_input_tokens` / `cache_read_input_tokens` in usage (NLM logs these as `[cache]` lines).

For non-Anthropic models (Qwen), `cache_control` fields should not be sent — they may be silently ignored or cause errors. OpenRouter handles caching implicitly at their proxy layer for many providers regardless of whether `cache_control` is present.

### Not to be confused with: OpenRouter response caching

A **separate** feature from Anthropic prompt caching. Response caching returns a byte-identical response for a repeated identical request and **zeroes all usage counters** (on the Messages endpoint, `usage.input_tokens` and `usage.output_tokens` report `0`). It keys on (API key, model, endpoint, streaming mode, full request body), so it rarely hits for NLM's unique streaming conversations. Mentioned only so a `0`-token usage row in logs isn't misread as a prompt-cache hit.

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

**`eager_input_streaming`** (provider option) — emits tool-argument deltas more eagerly during streaming. Set via `extra_body={"provider": {"eager_input_streaming": true}}` (or `providerOptions.openrouter` in the TS SDK). Surfaced in [ai-sdk-provider#111](https://github.com/OpenRouterTeam/ai-sdk-provider/issues/111) for tool-call streaming responsiveness — potentially relevant to stream-termination behavior.

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

OpenRouter may route requests to different backends (direct Anthropic, Bedrock, Vertex, Azure) depending on availability. Control routing via the `provider` object in the request body:

| Field | Type | Purpose |
|-------|------|---------|
| `order` | string[] | Try these provider slugs in order, e.g. `["anthropic"]` |
| `only` / `ignore` | string[] | Allowlist / denylist provider slugs |
| `allow_fallbacks` | bool (default `true`) | Permit backups when the primary is down |
| `require_parameters` | bool (default `false`) | Only use providers that support every parameter you sent |
| `data_collection` | `"allow"`\|`"deny"` | Exclude providers that may store data |
| `zdr` | bool | **Restrict routing to ZDR (Zero-Data-Retention) endpoints only** |
| `sort` | string | `"price"` \| `"throughput"` \| `"latency"` |

```json
{"provider": {"order": ["Anthropic"]}}        // pin backend
{"provider": {"zdr": true}}                     // hard-enforce ZDR per request
{"provider": {"data_collection": "deny"}}       // exclude data-retaining providers
```

**ZDR (primary NLM motivation):** `zdr: true` enforces Zero-Data-Retention **per request** from code — a hard guarantee, not just an account-level toggle. This is the code-level mechanism behind "ZDR without hoops."

**Backend variance:** pinning `provider.order` is only needed where behavior differs across backends. For NLM that's **not** caching (explicit per-block breakpoints work everywhere — see Prompt Caching) and **not** basic thinking. It *could* matter for interleaved-thinking if backend support varies.

**Passing `provider` via the Anthropic SDK:** the SDK has no native `provider` field — send it through `extra_body={"provider": {"zdr": true}}` on the request.

### App-identification / routing headers
- `HTTP-Referer`, `X-Title` — app identification (see Required Headers).
- `X-OpenRouter-Experimental-Metadata: enabled` — surfaces routing details under `openrouter_metadata` in the response (which backend served the request, etc.).
- `X-Generation-Id` (response) — query generation stats afterward.

## Rate Limiting

- Limits are **model-specific** and **per-account** (not per API key)
- HTTP `429` when rate limited, `402` when credits exhausted
- Free model variants (`:free` suffix) have lower limits
- No difference in rate limiting between the two endpoints
