from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ModelConfigCreate(BaseModel):
    provider_name: str = Field(..., min_length=1, max_length=128)
    provider_type: str = Field(default="OPENAI_COMPATIBLE")
    base_url: str = Field(..., min_length=1, max_length=512)
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1, max_length=128)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=128, le=32768)
    timeout: int = Field(default=30, ge=5, le=120)
    is_enabled: bool = True
    is_default: bool = False
    is_fallback: bool = False


class ModelConfigUpdate(BaseModel):
    provider_name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout: int | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None
    is_fallback: bool | None = None


class ModelConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_name: str
    provider_type: str
    base_url: str
    api_key_masked: str
    model_name: str
    temperature: float
    max_tokens: int
    timeout: int
    is_enabled: bool
    is_default: bool
    is_fallback: bool
    created_at: datetime
    updated_at: datetime


class ConnectionTestRequest(BaseModel):
    provider_type: str = "OPENAI_COMPATIBLE"
    base_url: str
    api_key: str | None = None
    model_name: str
    timeout: int = 20
    model_config_id: int | None = None  # If testing an existing configured model


class ConnectionTestResult(BaseModel):
    status: str  # "Connected", "Authentication Failed", "Model Not Found", "Timeout", "Network Error", "Other Error"
    code: str    # "CONNECTED", "AUTH_FAILED", "MODEL_NOT_FOUND", "TIMEOUT", "NETWORK_ERROR", "OTHER_ERROR"
    latency_ms: int = 0
    message: str


class ConversationCreate(BaseModel):
    title: str | None = None
    meet_id: int | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    user_id: int
    user_role: str
    meet_id: int | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    role: str
    content: str
    model_name: str | None = None
    provider_type: str | None = None
    tool_calls: Any | None = None
    token_usage: Any | None = None
    created_at: datetime


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., min_length=1)
    meet_id: int | None = None
    event_id: int | None = None
    page_context: str | None = None  # e.g. "results", "schedules", "rope", "events"
    stream: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: int
    content: str
    tool_calls: list[dict] | None = None
    token_usage: dict | None = None
    model: str | None = None
    provider: str | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str | None = None
    user_id: int | None = None
    user_role: str | None = None
    action_type: str
    provider: str | None = None
    model: str | None = None
    tool_name: str | None = None
    tool_arguments: Any | None = None
    tool_result_summary: str | None = None
    success: bool
    error_message: str | None = None
    latency_ms: int
    token_usage: Any | None = None
    created_at: datetime


class AnomalyReportItem(BaseModel):
    result_id: int
    event_id: int
    event_name: str
    round_name: str
    participant_name: str
    student_no: str | None = None
    college: str | None = None
    field: str
    value: Any
    anomaly_level: str  # LOW, MEDIUM, HIGH
    issue_type: str
    reason: str
    suggested_action: str


class AnomalyReport(BaseModel):
    total_scanned: int
    anomaly_count: int
    high_count: int
    medium_count: int
    low_count: int
    items: list[AnomalyReportItem]


class AIStatsOut(BaseModel):
    total_conversations: int
    total_messages: int
    total_tool_calls: int
    total_tokens: int
    avg_latency_ms: int
    success_rate: float
