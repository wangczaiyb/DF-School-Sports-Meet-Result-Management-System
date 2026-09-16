from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import developer_only, get_current_user, manager_only
from ..models import Role, User
from ..services import audit
from .anomaly import detect_result_anomalies
from .gateway import LLMGateway
from .models import AIAuditLog, AIConversation, AIMessage, AIModelConfig, AIToolLog
from .prompts import PromptManager
from .schemas import (
    AIStatsOut,
    AnomalyReport,
    AuditLogOut,
    ChatRequest,
    ChatResponse,
    ConnectionTestRequest,
    ConnectionTestResult,
    ConversationCreate,
    ConversationOut,
    MessageOut,
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
)
from .security import decrypt_api_key, encrypt_api_key, is_masked_key, mask_api_key
from .services import (
    delete_user_conversation,
    execute_chat,
    execute_stream_chat,
    get_conversation_messages,
    get_or_create_conversation,
    list_user_conversations,
)

router = APIRouter(prefix="/ai", tags=["AI Copilot"])


# ==============================================================================
# 1. Model Provider Management (DEVELOPER Only)
# ==============================================================================
@router.get("/models", response_model=list[ModelConfigOut])
def list_models(_admin: User = Depends(developer_only), db: Session = Depends(get_db)):
    """List configured LLM providers and models (DEVELOPER only)."""
    return list(db.scalars(select(AIModelConfig).order_by(AIModelConfig.id.desc())))


@router.post("/models", response_model=ModelConfigOut)
def create_model(
    data: ModelConfigCreate,
    admin: User = Depends(developer_only),
    db: Session = Depends(get_db),
):
    """Register a new LLM provider model (DEVELOPER only)."""
    if data.is_default:
        # Untag other defaults
        for other in db.scalars(select(AIModelConfig).where(AIModelConfig.is_default == True)):
            other.is_default = False

    ciphertext = encrypt_api_key(data.api_key)
    masked = mask_api_key(data.api_key)

    config = AIModelConfig(
        provider_name=data.provider_name.strip(),
        provider_type=data.provider_type.upper(),
        base_url=data.base_url.strip(),
        api_key_ciphertext=ciphertext,
        api_key_masked=masked,
        model_name=data.model_name.strip(),
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        timeout=data.timeout,
        is_enabled=data.is_enabled,
        is_default=data.is_default,
        is_fallback=data.is_fallback,
        created_by_id=admin.id,
    )
    db.add(config)
    db.flush()

    audit(
        db,
        admin,
        "CREATE_AI_MODEL",
        "ai_model_config",
        config.id,
        after={"provider": config.provider_name, "model": config.model_name, "type": config.provider_type},
    )
    db.commit()
    db.refresh(config)
    return config


@router.put("/models/{config_id}", response_model=ModelConfigOut)
def update_model(
    config_id: int,
    data: ModelConfigUpdate,
    admin: User = Depends(developer_only),
    db: Session = Depends(get_db),
):
    """Update LLM provider model configuration (DEVELOPER only)."""
    config = db.get(AIModelConfig, config_id)
    if not config:
        raise HTTPException(404, "大模型配置不存在")

    before_snapshot = {
        "provider": config.provider_name,
        "model": config.model_name,
        "enabled": config.is_enabled,
        "is_default": config.is_default,
    }

    if data.is_default:
        for other in db.scalars(select(AIModelConfig).where(AIModelConfig.id != config_id, AIModelConfig.is_default == True)):
            other.is_default = False

    if data.provider_name is not None:
        config.provider_name = data.provider_name.strip()
    if data.provider_type is not None:
        config.provider_type = data.provider_type.upper()
    if data.base_url is not None:
        config.base_url = data.base_url.strip()
    if data.model_name is not None:
        config.model_name = data.model_name.strip()
    if data.temperature is not None:
        config.temperature = data.temperature
    if data.max_tokens is not None:
        config.max_tokens = data.max_tokens
    if data.timeout is not None:
        config.timeout = data.timeout
    if data.is_enabled is not None:
        config.is_enabled = data.is_enabled
    if data.is_default is not None:
        config.is_default = data.is_default
    if data.is_fallback is not None:
        config.is_fallback = data.is_fallback

    # API key update only if new key provided and not masked placeholder
    if data.api_key and not is_masked_key(data.api_key):
        config.api_key_ciphertext = encrypt_api_key(data.api_key)
        config.api_key_masked = mask_api_key(data.api_key)

    audit(
        db,
        admin,
        "UPDATE_AI_MODEL",
        "ai_model_config",
        config.id,
        before=before_snapshot,
        after={"provider": config.provider_name, "model": config.model_name, "enabled": config.is_enabled},
    )
    db.commit()
    db.refresh(config)
    return config


@router.delete("/models/{config_id}")
def delete_model(
    config_id: int,
    admin: User = Depends(developer_only),
    db: Session = Depends(get_db),
):
    """Delete LLM provider model configuration (DEVELOPER only)."""
    config = db.get(AIModelConfig, config_id)
    if not config:
        raise HTTPException(404, "大模型配置不存在")

    audit(
        db,
        admin,
        "DELETE_AI_MODEL",
        "ai_model_config",
        config_id,
        before={"provider": config.provider_name, "model": config.model_name},
    )
    db.delete(config)
    db.commit()
    return {"message": f"已删除模型服务配置: {config.provider_name}"}


@router.post("/models/test-connection", response_model=ConnectionTestResult)
async def test_connection(
    data: ConnectionTestRequest,
    _admin: User = Depends(developer_only),
    db: Session = Depends(get_db),
):
    """Test model provider connectivity (DEVELOPER only)."""
    # If testing an existing config
    if data.model_config_id:
        cfg = db.get(AIModelConfig, data.model_config_id)
        if not cfg:
            raise HTTPException(404, "模型配置不存在")
        adapter = LLMGateway.create_adapter_from_config(cfg)
    else:
        if not data.api_key:
            raise HTTPException(422, "测试连接需提供 API Key")
        adapter = LLMGateway.create_adhoc_adapter(data)

    return await adapter.test_connection()


# ==============================================================================
# 2. Conversation & Chat Endpoints (All Authenticated Users)
# ==============================================================================
@router.get("/conversations", response_model=list[ConversationOut])
def get_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current user's isolated AI conversations."""
    return list_user_conversations(db, user)


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new AI conversation for current user."""
    conv = get_or_create_conversation(db, user, title=data.title, meet_id=data.meet_id)
    return {
        "id": conv.id,
        "title": conv.title,
        "user_id": conv.user_id,
        "user_role": conv.user_role,
        "meet_id": conv.meet_id,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "message_count": 0,
    }


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def get_messages(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch message history for a user conversation."""
    return get_conversation_messages(db, user, conv_id)


@router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user conversation and its message history."""
    success = delete_user_conversation(db, user, conv_id)
    if not success:
        raise HTTPException(404, "对话不存在或无权删除")
    return {"message": "对话已删除"}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Standard non-streaming chat with RBAC tool calling."""
    try:
        return await execute_chat(db, user, req)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"AI 处理失败: {str(e)}") from e


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Server-Sent Events (SSE) streaming chat with real-time tool calls."""
    return StreamingResponse(
        execute_stream_chat(db, user, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==============================================================================
# 3. Anomaly Detection, Prompts & Auditing
# ==============================================================================
@router.get("/anomalies", response_model=AnomalyReport)
def get_anomalies(
    event_id: int | None = Query(None),
    meet_id: int | None = Query(None),
    _staff: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Run AI-assisted anomaly detection on results (Staff only)."""
    return detect_result_anomalies(db, event_id=event_id, meet_id=meet_id)


@router.get("/suggested-prompts")
def get_suggested_prompts(user: User = Depends(get_current_user)):
    """Return role-aware suggested prompt pills."""
    return {
        "role": user.role,
        "prompts": PromptManager.get_suggested_prompts(user.role),
    }


@router.get("/audit-logs", response_model=list[AuditLogOut])
def get_ai_audit_logs(
    limit: int = Query(50, le=100),
    _admin: User = Depends(developer_only),
    db: Session = Depends(get_db),
):
    """List AI activity and tool calling audit logs (DEVELOPER only)."""
    return list(db.scalars(select(AIAuditLog).order_by(AIAuditLog.created_at.desc()).limit(limit)))


@router.get("/stats", response_model=AIStatsOut)
def get_ai_stats(
    _admin: User = Depends(developer_only),
    db: Session = Depends(get_db),
):
    """Overview statistics of AI platform usage (DEVELOPER only)."""
    total_convs = db.scalar(select(func.count(AIConversation.id))) or 0
    total_msgs = db.scalar(select(func.count(AIMessage.id))) or 0
    total_tools = db.scalar(select(func.count(AIToolLog.id))) or 0

    audit_records = list(db.scalars(select(AIAuditLog)))
    total_tokens = 0
    total_latency = 0
    success_count = 0

    for a in audit_records:
        if a.success:
            success_count += 1
        total_latency += a.latency_ms or 0
        if a.token_usage and isinstance(a.token_usage, dict):
            total_tokens += a.token_usage.get("total_tokens", 0)

    count = len(audit_records)
    avg_latency = int(total_latency / count) if count > 0 else 0
    success_rate = round((success_count / count) * 100, 1) if count > 0 else 100.0

    return {
        "total_conversations": total_convs,
        "total_messages": total_msgs,
        "total_tool_calls": total_tools,
        "total_tokens": total_tokens,
        "avg_latency_ms": avg_latency,
        "success_rate": success_rate,
    }
