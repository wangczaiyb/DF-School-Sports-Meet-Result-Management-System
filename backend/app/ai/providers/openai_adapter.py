from __future__ import annotations

import json
import time
from typing import AsyncIterator
import httpx

from .base import BaseProviderAdapter, LLMResponse, LLMStreamChunk
from ..schemas import ConnectionTestResult


class OpenAICompatibleAdapter(BaseProviderAdapter):
    """Adapter for OpenAI, DeepSeek, and any OpenAI-compatible LLM endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: int = 30,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        provider_type: str = "OPENAI_COMPATIBLE",
    ):
        super().__init__(base_url, api_key, model_name, timeout, temperature, max_tokens)
        self.provider_type = provider_type

    def _get_endpoint(self) -> str:
        url = self.base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        return url

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def test_connection(self) -> ConnectionTestResult:
        start_time = time.perf_counter()
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
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
                        message=f"成功连接至 {self.model_name} (耗时 {latency}ms)",
                    )
                elif res.status_code in (401, 403):
                    return ConnectionTestResult(
                        status="Authentication Failed",
                        code="AUTH_FAILED",
                        latency_ms=latency,
                        message=f"认证失败：API Key 无效或未授权 ({res.status_code})",
                    )
                elif res.status_code == 404:
                    return ConnectionTestResult(
                        status="Model Not Found",
                        code="MODEL_NOT_FOUND",
                        latency_ms=latency,
                        message=f"模型不存在或接口地址错误：{self.model_name} (404)",
                    )
                else:
                    return ConnectionTestResult(
                        status="Other Error",
                        code="OTHER_ERROR",
                        latency_ms=latency,
                        message=f"HTTP 状态码异常：{res.status_code} - {res.text[:200]}",
                    )
        except httpx.TimeoutException:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ConnectionTestResult(
                status="Timeout",
                code="TIMEOUT",
                latency_ms=latency,
                message=f"连接超时：超过 {self.timeout}s 未响应",
            )
        except (httpx.ConnectError, httpx.NetworkError) as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ConnectionTestResult(
                status="Network Error",
                code="NETWORK_ERROR",
                latency_ms=latency,
                message=f"网络错误：无法访问服务地址 ({str(e)[:150]})",
            )
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ConnectionTestResult(
                status="Other Error",
                code="OTHER_ERROR",
                latency_ms=latency,
                message=f"测试失败：{str(e)[:150]}",
            )

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        payload: dict = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(endpoint, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()

            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            raw_tool_calls = msg.get("tool_calls")
            parsed_tools = None

            if raw_tool_calls:
                parsed_tools = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args_raw = fn.get("arguments", "{}")
                    try:
                        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except Exception:
                        fn_args = {}
                    parsed_tools.append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args,
                        },
                    })

            usage = data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            return LLMResponse(
                content=content,
                tool_calls=parsed_tools,
                token_usage=usage,
                model=data.get("model", self.model_name),
                provider=self.provider_type,
            )

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMStreamChunk]:
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        payload: dict = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                response.raise_for_status()
                tool_calls_accumulator: dict[int, dict] = {}

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except Exception:
                            continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            # Might be usage chunk in some APIs
                            if "usage" in chunk:
                                yield LLMStreamChunk(token_usage=chunk["usage"])
                            continue

                        choice = choices[0]
                        delta = choice.get("delta", {})
                        text = delta.get("content") or ""
                        finish_reason = choice.get("finish_reason")

                        # Handle streaming tool calls
                        delta_tool_calls = delta.get("tool_calls")
                        if delta_tool_calls:
                            for tc_delta in delta_tool_calls:
                                idx = tc_delta.get("index", 0)
                                if idx not in tool_calls_accumulator:
                                    tool_calls_accumulator[idx] = {
                                        "id": tc_delta.get("id", f"call_{idx}"),
                                        "type": "function",
                                        "function": {
                                            "name": tc_delta.get("function", {}).get("name", ""),
                                            "arguments": "",
                                        },
                                    }
                                fn = tc_delta.get("function", {})
                                if fn.get("name"):
                                    tool_calls_accumulator[idx]["function"]["name"] = fn["name"]
                                if fn.get("arguments"):
                                    tool_calls_accumulator[idx]["function"]["arguments"] += fn["arguments"]

                        is_finish = finish_reason is not None
                        formatted_tools = None
                        if is_finish and tool_calls_accumulator:
                            formatted_tools = []
                            for idx in sorted(tool_calls_accumulator.keys()):
                                acc = tool_calls_accumulator[idx]
                                raw_args = acc["function"]["arguments"]
                                try:
                                    parsed_args = json.loads(raw_args) if raw_args else {}
                                except Exception:
                                    parsed_args = {}
                                formatted_tools.append({
                                    "id": acc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": acc["function"]["name"],
                                        "arguments": parsed_args,
                                    },
                                })

                        yield LLMStreamChunk(
                            delta_text=text,
                            delta_tool_calls=formatted_tools,
                            is_finish=is_finish,
                            finish_reason=finish_reason,
                            token_usage=chunk.get("usage"),
                        )
