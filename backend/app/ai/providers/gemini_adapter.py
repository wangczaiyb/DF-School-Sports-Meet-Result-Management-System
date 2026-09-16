from __future__ import annotations

import json
import time
from typing import AsyncIterator
import httpx

from .base import BaseProviderAdapter, LLMResponse, LLMStreamChunk
from ..schemas import ConnectionTestResult


class GeminiAdapter(BaseProviderAdapter):
    """Adapter for Google Gemini REST API (generateContent)."""

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

    def _get_url(self) -> str:
        url = self.base_url.rstrip("/")
        # If user entered standard googleapis base or custom reverse proxy
        if "generateContent" not in url:
            if not url.endswith("/v1beta"):
                url = f"{url}/v1beta"
            url = f"{url}/models/{self.model_name}:generateContent"
        return f"{url}?key={self.api_key}"

    async def test_connection(self) -> ConnectionTestResult:
        start_time = time.perf_counter()
        url = self._get_url()
        payload = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 5},
        }

        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 15)) as client:
                res = await client.post(url, json=payload)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    return ConnectionTestResult(
                        status="Connected",
                        code="CONNECTED",
                        latency_ms=latency,
                        message=f"成功连接至 Gemini ({self.model_name})",
                    )
                elif res.status_code in (400, 403):
                    return ConnectionTestResult(
                        status="Authentication Failed",
                        code="AUTH_FAILED",
                        latency_ms=latency,
                        message="认证失败：Google API Key 无效或未授权",
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
                        message=f"Gemini 接口异常：{res.status_code} - {res.text[:150]}",
                    )
        except httpx.TimeoutException:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ConnectionTestResult(status="Timeout", code="TIMEOUT", latency_ms=latency, message="连接超时")
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ConnectionTestResult(status="Network Error", code="NETWORK_ERROR", latency_ms=latency, message=str(e)[:150])

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        url = self._get_url()
        gemini_contents = []
        system_instruction = None

        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            if m.get("role") == "system":
                system_instruction = {"parts": [{"text": m.get("content", "")}]}
            else:
                gemini_contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

        payload: dict = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()

            candidates = data.get("candidates", [])
            text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)

            usage = data.get("usageMetadata", {})
            return LLMResponse(
                content=text,
                tool_calls=None,
                token_usage={
                    "prompt_tokens": usage.get("promptTokenCount", 0),
                    "completion_tokens": usage.get("candidatesTokenCount", 0),
                    "total_tokens": usage.get("totalTokenCount", 0),
                },
                model=self.model_name,
                provider="GEMINI",
            )

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMStreamChunk]:
        res = await self.chat(messages, tools)
        yield LLMStreamChunk(
            delta_text=res.content,
            is_finish=True,
            finish_reason="stop",
            token_usage=res.token_usage,
        )
