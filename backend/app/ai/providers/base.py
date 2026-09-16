from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from ..schemas import ConnectionTestResult


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[dict] | None = None
    token_usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    model: str = ""
    provider: str = ""


@dataclass
class LLMStreamChunk:
    delta_text: str = ""
    delta_tool_calls: list[dict] | None = None
    is_finish: bool = False
    finish_reason: str | None = None
    token_usage: dict | None = None


class BaseProviderAdapter(ABC):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: int = 30,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Test provider connectivity and credentials."""
        pass

    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        """Send chat completion request (non-streaming)."""
        pass

    @abstractmethod
    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream chat completion tokens and tool calls."""
        pass
