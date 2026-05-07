"""
OpenAI-compat provider for OpenRouter models that use OpenAI wire format.

Used for Qwen hybrid models where reasoning suppression requires the OpenAI-compat
endpoint (/v1/chat/completions) and explicit `reasoning: {enabled: false}`.
The Anthropic-compat endpoint silently ignores the reasoning parameter for these models.
"""

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from shared.chat_config import load_config

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenAIProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _translate_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Anthropic-format messages to OpenAI format."""
        result = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            if isinstance(content, str):
                result.append({"role": role, "content": content})
                continue

            # content is a list of blocks (Anthropic format)
            if role == "assistant":
                # May contain text, thinking, tool_use blocks
                text_parts = []
                tool_calls = []
                for block in content:
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block["text"])
                    elif btype == "thinking":
                        pass  # drop thinking blocks — not re-injectable via OpenAI format
                    elif btype == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block.get("input", {})),
                            },
                        })
                out: dict[str, Any] = {"role": "assistant", "content": " ".join(text_parts) or None}
                if tool_calls:
                    out["tool_calls"] = tool_calls
                result.append(out)

            elif role == "user":
                # May contain text and tool_result blocks
                text_parts = []
                for block in content:
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block["text"])
                    elif btype == "tool_result":
                        tool_content = block.get("content", "")
                        if isinstance(tool_content, list):
                            tool_content = " ".join(
                                b["text"] for b in tool_content if b.get("type") == "text"
                            )
                        result.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": tool_content,
                        })
                if text_parts:
                    result.append({"role": "user", "content": " ".join(text_parts)})
            else:
                result.append({"role": role, "content": str(content)})

        return result

    def _translate_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Anthropic tool schema to OpenAI function schema."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in tools
        ]

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        thinking_enabled: bool,
    ) -> dict[str, Any]:
        global_thinking_enabled = load_config().get("thinking_enabled", True)
        effective_thinking = thinking_enabled and global_thinking_enabled

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system_prompt}, *self._translate_messages(messages)],
            "stream": True,
        }
        if tools:
            payload["tools"] = self._translate_tools(tools)
        if effective_thinking:
            payload["reasoning"] = {"effort": "high"}
            payload["max_tokens"] = max(max_tokens, 16192)
        else:
            payload["reasoning"] = {"enabled": False}  # Qwen hybrid models default to thinking-on; must suppress explicitly

        return payload

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        thinking_enabled: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        global_thinking_enabled = load_config().get("thinking_enabled", True)
        effective_thinking = thinking_enabled and global_thinking_enabled
        payload = self._build_payload(messages, system_prompt, tools, max_tokens, thinking_enabled)

        logger.info(
            f"[openrouter-openai] stream_chat model={self.model} "
            f"thinking_req={thinking_enabled} global_flag={global_thinking_enabled} "
            f"effective_thinking={effective_thinking}"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        accumulated_reasoning = ""
        current_tool_id: str | None = None
        current_tool_name: str | None = None
        current_tool_args = ""

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or line.startswith(":"):
                            continue  # skip SSE keepalives
                        if line.startswith("data: "):
                            data = line[6:]
                        else:
                            data = line
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        choice = chunk.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")

                        # Reasoning / thinking delta
                        reasoning = delta.get("reasoning")
                        if reasoning:
                            accumulated_reasoning += reasoning
                            yield {"type": "thinking_delta", "content": reasoning}

                        # Text delta
                        text = delta.get("content")
                        if text:
                            yield {"type": "text", "content": text}

                        # Tool call deltas
                        tool_calls = delta.get("tool_calls")
                        if tool_calls:
                            for tc in tool_calls:
                                fn = tc.get("function", {})
                                if tc.get("id"):
                                    # New tool call starting
                                    if current_tool_id:
                                        # Flush previous
                                        try:
                                            parsed_input = json.loads(current_tool_args)
                                        except json.JSONDecodeError:
                                            parsed_input = {}
                                        yield {
                                            "type": "tool_use",
                                            "id": current_tool_id,
                                            "name": current_tool_name,
                                            "input": parsed_input,
                                        }
                                    current_tool_id = tc["id"]
                                    current_tool_name = fn.get("name", "")
                                    current_tool_args = fn.get("arguments", "")
                                    yield {
                                        "type": "tool_use_start",
                                        "id": current_tool_id,
                                        "name": current_tool_name,
                                    }
                                else:
                                    # Argument fragment
                                    args_frag = fn.get("arguments", "")
                                    if args_frag:
                                        current_tool_args += args_frag
                                        yield {"type": "tool_input_delta", "content": args_frag}

                        if finish_reason == "tool_calls" and current_tool_id:
                            try:
                                parsed_input = json.loads(current_tool_args)
                            except json.JSONDecodeError:
                                parsed_input = {}
                            yield {
                                "type": "tool_use",
                                "id": current_tool_id,
                                "name": current_tool_name,
                                "input": parsed_input,
                            }
                            current_tool_id = None
                            current_tool_name = None
                            current_tool_args = ""

                        if finish_reason == "error":
                            error_msg = chunk.get("error", {}).get("message", "Unknown error")
                            logger.error(f"[openrouter-openai] finish_reason=error model={self.model}: {error_msg}")
                            yield {"type": "error", "content": error_msg}
                            return

        except httpx.HTTPStatusError as e:
            logger.error(f"[openrouter-openai] HTTP error model={self.model}: {e.response.status_code}")
            yield {"type": "error", "content": f"OpenRouter HTTP error: {e.response.status_code}"}
            return
        except httpx.RequestError as e:
            logger.error(f"[openrouter-openai] Connection error model={self.model}: {e}")
            yield {"type": "error", "content": f"Cannot connect to OpenRouter: {e}"}
            return
        except Exception as e:
            logger.error(f"[openrouter-openai] Unexpected error model={self.model}: {e}")
            yield {"type": "error", "content": str(e)}
            return

        if not effective_thinking and accumulated_reasoning:
            logger.warning(
                f"[openrouter-openai] suppression ignored: model={self.model} "
                f"effective_thinking=False reasoning_chars={len(accumulated_reasoning)}"
            )

        if accumulated_reasoning:
            yield {
                "type": "thinking_block",
                "thinking": accumulated_reasoning,
                "signature": "",
            }

        yield {"type": "done"}
