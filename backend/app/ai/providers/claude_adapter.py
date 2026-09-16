from __future__ import annotations

import json
import time
from typing import AsyncIterator
import httpx

from .base import BaseProviderAdapter, LLMResponse, LLMStreamChunk
from ..schemas import ConnectionTestResult


class ClaudeAdapter(BaseProviderAdapter):
    """Adapter for Anthropic Claude API (/v1/messages)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: int = 30,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        super().__init__(base_url, api_key, model_name, timeout, temperature, max_tokens)

    def _get_endpoint(self) -> str:
        url = self.base_url.rstrip("/")
        if not url.endswith("/messages"):
            url = f"{url}/messages"
        return url

    def _get_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _prepare_claude_payload(self, messages: list[dict], tools: list[dict] | None = None) -> tuple[str | None, list[dict], list[dict] | None]:
        system_prompt = None
        user_assistant_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_prompt = (system_prompt + "\n" + m.get("content", "")) if system_prompt else m.get("content", "")
            else:
                user_assistant_messages.append({"role": m["role"], "content": m.get("content", "")})

        claude_tools = None
        if tools:
            claude_tools = []
            for t in tools:
                fn = t.get("function", {})
                claude_tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                })

        return system_prompt, user_assistant_messages, claude_tools

    async def test_connection(self) -> ConnectionTestResult:
        start_time = time.perf_counter()
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        payload = {
            "model": self.model_name,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "ping"}],
        }

        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 15)) as client:
                res = await client.post(endpoint, json=payload, headers=headers)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    return ConnectionTestResult(
                        status="Connected",
                        code="CONNECTED",
                        latency_ms=latency,
                        message=f"成功连接至 Claude ({self.model_name})",
                    )
                elif res.status_code in (401, 403):
                    return ConnectionTestResult(
                        status="Authentication Failed",
                        code="AUTH_FAILED",
                        latency_ms=latency,
                        message="认证失败：x-api-key 无效",
                    )
                elif res.status_code == 404:
                    return ConnectionTestResult(
                        status="Model Not Found",
                        code="MODEL_NOT_FOUND",
                        latency_ms=latency,
                        message=f"模型不存在：{self.model_name}",
                    )
                else:
                    return ConnectionTestResult(
                        status="Other Error",
                        code="OTHER_ERROR",
                        latency_ms=latency,
                        message=f"状态码异常：{res.status_code} - {res.text[:150]}",
                    )
        except httpx.TimeoutException:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ConnectionTestResult(status="Timeout", code="TIMEOUT", latency_ms=latency, message="连接超时")
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ConnectionTestResult(status="Network Error", code="NETWORK_ERROR", latency_ms=latency, message=str(e)[:150])

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        system_prompt, u_messages, claude_tools = self._prepare_claude_payload(messages, tools)

        payload: dict = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "messages": u_messages,
            "temperature": self.temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if claude_tools:
            payload["tools"] = claude_tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(endpoint, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()

            content_text = ""
            parsed_tools = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content_text += block.get("text", "")
                elif block.get("type") == "tool_use":
                    parsed_tools.append({
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": block.get("input", {}),
                        },
                    })

            usage = data.get("usage", {})
            return LLMResponse(
                content=content_text,
                tool_calls=parsed_tools or None,
                token_usage={
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                },
                model=data.get("model", self.model_name),
                provider="CLAUDE",
            )

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMStreamChunk]:
        # Fallback to non-stream for simplicity or stream response
        res = await self.chat(messages, tools)
        yield LLMStreamChunk(
            delta_text=res.content,
            delta_tool_calls=res.tool_calls,
            is_finish=True,
            finish_reason="stop",
            token_usage=res.token_usage,
        )
