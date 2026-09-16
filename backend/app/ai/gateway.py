from __future__ import annotations

import logging
from typing import AsyncIterator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AIModelConfig, ProviderType
from .providers.base import BaseProviderAdapter, LLMResponse, LLMStreamChunk
from .providers.openai_adapter import OpenAICompatibleAdapter
from .providers.claude_adapter import ClaudeAdapter
from .providers.gemini_adapter import GeminiAdapter
from .schemas import ConnectionTestRequest, ConnectionTestResult
from .security import decrypt_api_key

logger = logging.getLogger(__name__)


class LLMGateway:
    """Unified LLM Gateway with multi-provider routing and fallback management."""

    @staticmethod
    def create_adapter_from_config(config: AIModelConfig) -> BaseProviderAdapter:
        plain_key = decrypt_api_key(config.api_key_ciphertext)
        pt = config.provider_type.upper()

        if pt == ProviderType.CLAUDE:
            return ClaudeAdapter(
                base_url=config.base_url,
                api_key=plain_key,
                model_name=config.model_name,
                timeout=config.timeout,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
        elif pt == ProviderType.GEMINI:
            return GeminiAdapter(
                base_url=config.base_url,
                api_key=plain_key,
                model_name=config.model_name,
                timeout=config.timeout,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
        else:
            # OPENAI, DEEPSEEK, OPENAI_COMPATIBLE, CUSTOM
            return OpenAICompatibleAdapter(
                base_url=config.base_url,
                api_key=plain_key,
                model_name=config.model_name,
                timeout=config.timeout,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                provider_type=pt,
            )

    @staticmethod
    def create_adhoc_adapter(data: ConnectionTestRequest) -> BaseProviderAdapter:
        pt = data.provider_type.upper()
        if pt == ProviderType.CLAUDE:
            return ClaudeAdapter(
                base_url=data.base_url,
                api_key=data.api_key or "",
                model_name=data.model_name,
                timeout=data.timeout,
            )
        elif pt == ProviderType.GEMINI:
            return GeminiAdapter(
                base_url=data.base_url,
                api_key=data.api_key or "",
                model_name=data.model_name,
                timeout=data.timeout,
            )
        else:
            return OpenAICompatibleAdapter(
                base_url=data.base_url,
                api_key=data.api_key or "",
                model_name=data.model_name,
                timeout=data.timeout,
                provider_type=pt,
            )

    @classmethod
    def get_active_model_config(cls, db: Session) -> AIModelConfig | None:
        """Find the active default model, or first enabled model."""
        default_model = db.scalar(
            select(AIModelConfig).where(AIModelConfig.is_enabled == True, AIModelConfig.is_default == True)
        )
        if default_model:
            return default_model
        return db.scalar(select(AIModelConfig).where(AIModelConfig.is_enabled == True).order_by(AIModelConfig.id))

    @classmethod
    def get_fallback_model_config(cls, db: Session, exclude_id: int | None = None) -> AIModelConfig | None:
        """Find fallback model when primary model fails."""
        stmt = select(AIModelConfig).where(AIModelConfig.is_enabled == True, AIModelConfig.is_fallback == True)
        if exclude_id:
            stmt = stmt.where(AIModelConfig.id != exclude_id)
        fallback = db.scalar(stmt)
        if not fallback and exclude_id:
            # Pick any other enabled model as fallback candidate
            fallback = db.scalar(select(AIModelConfig).where(AIModelConfig.is_enabled == True, AIModelConfig.id != exclude_id))
        return fallback

    @classmethod
    async def chat(
        cls,
        db: Session,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[LLMResponse, AIModelConfig]:
        """Execute chat completion with automatic fallback."""
        primary_config = cls.get_active_model_config(db)
        if not primary_config:
            raise RuntimeError("系统尚未配置或启用任何大模型服务，请管理员前往【AI 智能中心】完成配置")

        primary_adapter = cls.create_adapter_from_config(primary_config)
        try:
            resp = await primary_adapter.chat(messages, tools)
            return resp, primary_config
        except Exception as e:
            logger.warning(f"主模型 [{primary_config.provider_name} / {primary_config.model_name}] 调用失败: {e}")
            fallback_config = cls.get_fallback_model_config(db, exclude_id=primary_config.id)
            if fallback_config:
                logger.info(f"正在自动切换至备用降级模型: [{fallback_config.provider_name} / {fallback_config.model_name}]")
                fallback_adapter = cls.create_adapter_from_config(fallback_config)
                resp = await fallback_adapter.chat(messages, tools)
                return resp, fallback_config
            raise RuntimeError(f"模型调用失败且无可用备用模型: {e}") from e

    @classmethod
    async def stream_chat(
        cls,
        db: Session,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[AsyncIterator[LLMStreamChunk], AIModelConfig]:
        """Execute stream chat completion."""
        primary_config = cls.get_active_model_config(db)
        if not primary_config:
            raise RuntimeError("系统尚未配置或启用任何大模型服务，请管理员前往【AI 智能中心】完成配置")

        primary_adapter = cls.create_adapter_from_config(primary_config)
        try:
            return primary_adapter.stream_chat(messages, tools), primary_config
        except Exception as e:
            fallback_config = cls.get_fallback_model_config(db, exclude_id=primary_config.id)
            if fallback_config:
                fallback_adapter = cls.create_adapter_from_config(fallback_config)
                return fallback_adapter.stream_chat(messages, tools), fallback_config
            raise RuntimeError(f"流式模型调用失败: {e}") from e
