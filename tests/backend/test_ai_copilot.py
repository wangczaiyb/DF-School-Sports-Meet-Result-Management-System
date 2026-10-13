from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.ai.models import AIAuditLog, AIConversation, AIModelConfig, AIToolLog
from backend.app.ai.providers.base import LLMResponse
from backend.app.ai.security import decrypt_api_key, encrypt_api_key, mask_api_key
from backend.app.database import SessionLocal
from backend.app.main import app
from backend.app.models import Event, Registration, Result, Role, SportsMeet, User


@pytest.fixture
def client():
    return TestClient(app)


def _login(client: TestClient, kind: str, username: str, password: str) -> str:
    res = client.post(f"/api/v1/auth/{kind}-login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def dev_headers(client: TestClient):
    token = _login(client, "developer", "developer01", "Dev123456!")
    return _headers(token)


@pytest.fixture
def teacher_headers(client: TestClient):
    token = _login(client, "admin", "admin0001", "Admin123456!")
    return _headers(token)


@pytest.fixture
def scorer_headers(client: TestClient):
    token = _login(client, "admin", "admin0002", "Admin123456!")
    return _headers(token)


@pytest.fixture
def referee_headers(client: TestClient):
    token = _login(client, "admin", "admin0003", "Admin123456!")
    return _headers(token)


@pytest.fixture
def student_headers(client: TestClient):
    token = _login(client, "student", "2026001001", "DF2026001001")
    return _headers(token)


# ------------------------------------------------------------------------------
# 1. API Key Security & Encryption Unit Tests
# ------------------------------------------------------------------------------
def test_api_key_encryption_and_masking():
    plain = "sk-test1234567890abcdefghijklmnopqrstuvwxyz"
    ciphertext = encrypt_api_key(plain)
    assert ciphertext != plain
    assert decrypt_api_key(ciphertext) == plain

    masked = mask_api_key(plain)
    assert masked.startswith("sk-")
    assert masked.endswith("xyz")
    assert "**************" in masked
    assert plain not in masked


# ------------------------------------------------------------------------------
# 2. Model Configuration CRUD & Permission Guard
# ------------------------------------------------------------------------------
def test_model_config_crud_and_rbac(client: TestClient, dev_headers, student_headers, teacher_headers):
    # Student and Teacher should be denied access to AI models management
    assert client.get("/api/v1/ai/models", headers=student_headers).status_code == 403
    assert client.get("/api/v1/ai/models", headers=teacher_headers).status_code == 403

    # Developer creates a model
    create_payload = {
        "provider_name": "DeepSeek 官方 API",
        "provider_type": "DEEPSEEK",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-deepseek-super-secret-key-12345678",
        "model_name": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 2048,
        "timeout": 30,
        "is_enabled": True,
        "is_default": True,
        "is_fallback": False,
    }
    create_res = client.post("/api/v1/ai/models", headers=dev_headers, json=create_payload)
    assert create_res.status_code == 200, create_res.text
    created = create_res.json()
    config_id = created["id"]
    assert created["provider_name"] == "DeepSeek 官方 API"
    assert "sk-" in created["api_key_masked"]
    assert "super-secret" not in created["api_key_masked"]  # Key must be masked!
    assert "api_key_ciphertext" not in created  # Plain/ciphertext must not leak to frontend!

    # Verify database storage (ciphertext only)
    with SessionLocal() as db:
        row = db.get(AIModelConfig, config_id)
        assert row is not None
        assert row.api_key_ciphertext != create_payload["api_key"]
        assert decrypt_api_key(row.api_key_ciphertext) == create_payload["api_key"]

    # Developer updates model (e.g. changes temperature and leaves masked key)
    update_res = client.put(
        f"/api/v1/ai/models/{config_id}",
        headers=dev_headers,
        json={"temperature": 0.5, "api_key": created["api_key_masked"]},
    )
    assert update_res.status_code == 200
    assert update_res.json()["temperature"] == 0.5

    # Verify key was not corrupted by the masked placeholder
    with SessionLocal() as db:
        row = db.get(AIModelConfig, config_id)
        assert decrypt_api_key(row.api_key_ciphertext) == create_payload["api_key"]

    # Developer deletes model
    del_res = client.delete(f"/api/v1/ai/models/{config_id}", headers=dev_headers)
    assert del_res.status_code == 200


# ------------------------------------------------------------------------------
# 3. Connection Test
# ------------------------------------------------------------------------------
def test_connection_test_mocked(client: TestClient, dev_headers, student_headers):
    # Student forbidden
    assert client.post("/api/v1/ai/models/test-connection", headers=student_headers, json={"base_url": "http://test", "api_key": "k", "model_name": "m"}).status_code == 403

    # Mock successful connection
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 200
        res = client.post(
            "/api/v1/ai/models/test-connection",
            headers=dev_headers,
            json={
                "provider_type": "OPENAI_COMPATIBLE",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-mock-key-12345",
                "model_name": "gpt-4o-mini",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "Connected"
        assert data["code"] == "CONNECTED"

    # Mock auth failed (401)
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 401
        res = client.post(
            "/api/v1/ai/models/test-connection",
            headers=dev_headers,
            json={
                "provider_type": "DEEPSEEK",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "sk-wrong-key",
                "model_name": "deepseek-chat",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "Authentication Failed"
        assert data["code"] == "AUTH_FAILED"


# ------------------------------------------------------------------------------
# 4. Fallback Model Routing Mechanism
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fallback_model_routing():
    with SessionLocal() as db:
        # Create primary failing model
        primary = AIModelConfig(
            provider_name="Primary Fail",
            provider_type="OPENAI_COMPATIBLE",
            base_url="https://fail.example.com",
            api_key_ciphertext=encrypt_api_key("sk-primary"),
            api_key_masked="sk-***mary",
            model_name="primary-fail-model",
            is_enabled=True,
            is_default=True,
            is_fallback=False,
        )
        # Create backup fallback model
        backup = AIModelConfig(
            provider_name="Backup Fallback",
            provider_type="OPENAI_COMPATIBLE",
            base_url="https://backup.example.com",
            api_key_ciphertext=encrypt_api_key("sk-backup"),
            api_key_masked="sk-***kbackup",
            model_name="backup-model",
            is_enabled=True,
            is_default=False,
            is_fallback=True,
        )
        db.add_all([primary, backup])
        db.commit()
        p_id, b_id = primary.id, backup.id

    try:
        with SessionLocal() as db:
            from backend.app.ai.gateway import LLMGateway

            # Mock primary to fail, and backup to succeed
            async def mock_chat(messages, tools=None):
                raise RuntimeError("Primary provider down 503")

            async def mock_backup_chat(messages, tools=None):
                return LLMResponse(content="Fallback model reply", model="backup-model", provider="OPENAI_COMPATIBLE")

            with patch("backend.app.ai.providers.openai_adapter.OpenAICompatibleAdapter.chat", side_effect=[RuntimeError("Primary 503"), LLMResponse(content="Fallback success", model="backup-model", provider="OPENAI_COMPATIBLE")]):
                resp, used_config = await LLMGateway.chat(db, [{"role": "user", "content": "hello"}])
                assert resp.content == "Fallback success"
                assert used_config.id == b_id  # Automatically routed to backup model!
    finally:
        with SessionLocal() as db:
            p = db.get(AIModelConfig, p_id)
            b = db.get(AIModelConfig, b_id)
            if p: db.delete(p)
            if b: db.delete(b)
            db.commit()


# ------------------------------------------------------------------------------
# 5. Role-Aware Tool Calling & RBAC Sandboxing
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tool_calling_rbac():
    with SessionLocal() as db:
        from backend.app.ai.tools import tool_registry

        # Fetch users
        dev_user = db.scalar(select(User).where(User.role == Role.DEVELOPER))
        student_user = db.scalar(select(User).where(User.role == Role.STUDENT))
        teacher_user = db.scalar(select(User).where(User.role == Role.SPORTS_TEACHER))
        scorer_user = db.scalar(select(User).where(User.role == Role.SCORER))

        # A) Student can get own schedule and profile
        st_profile = await tool_registry.execute("get_current_user_profile", {}, student_user, db)
        assert "student_no" in st_profile
        assert st_profile["role"] == "STUDENT"

        st_sched = await tool_registry.execute("get_student_schedule", {}, student_user, db)
        assert "items" in st_sched
        assert st_sched["student_name"] == st_profile["name"]

        # B) Student CANNOT get pending reviews or audit logs (Permission Denied)
        pending_res = await tool_registry.execute("get_pending_reviews", {}, student_user, db)
        assert "error" in pending_res
        assert pending_res["code"] == "PERMISSION_DENIED"

        audit_res = await tool_registry.execute("get_audit_logs", {}, student_user, db)
        assert "error" in audit_res
        assert audit_res["code"] == "PERMISSION_DENIED"

        # C) Teacher can get meets, rankings, pending reviews
        meet_res = await tool_registry.execute("get_sports_meets", {}, teacher_user, db)
        assert "meets" in meet_res
        assert len(meet_res["meets"]) > 0
        meet_id = meet_res["meets"][0]["id"]

        rank_res = await tool_registry.execute("get_rankings", {"meet_id": meet_id}, teacher_user, db)
        assert "rankings" in rank_res

        t_pending = await tool_registry.execute("get_pending_reviews", {"meet_id": meet_id}, teacher_user, db)
        assert "total_pending" in t_pending

        # D) Developer can get audit logs
        dev_audit = await tool_registry.execute("get_audit_logs", {"limit": 5}, dev_user, db)
        assert "logs" in dev_audit


# ------------------------------------------------------------------------------
# 6. Conversation Isolation
# ------------------------------------------------------------------------------
def test_conversation_isolation(client: TestClient, student_headers, teacher_headers):
    # Student creates a conversation
    create_res = client.post("/api/v1/ai/conversations", headers=student_headers, json={"title": "学生私密会话"})
    assert create_res.status_code == 200
    conv_id = create_res.json()["id"]

    # Teacher cannot view or delete Student's conversation
    assert client.get(f"/api/v1/ai/conversations/{conv_id}/messages", headers=teacher_headers).json() == []
    del_forbidden = client.delete(f"/api/v1/ai/conversations/{conv_id}", headers=teacher_headers)
    assert del_forbidden.status_code == 404

    # Student can see and delete own conversation
    del_ok = client.delete(f"/api/v1/ai/conversations/{conv_id}", headers=student_headers)
    assert del_ok.status_code == 200


# ------------------------------------------------------------------------------
# 7. AI-Assisted Anomaly Detection Engine Test
# ------------------------------------------------------------------------------
def test_result_anomaly_detection(client: TestClient, teacher_headers):
    with SessionLocal() as db:
        ev = db.scalar(select(Event).where(Event.name.contains("100")))
        if not ev:
            ev = db.scalar(select(Event))
        event_id = ev.id

        # Insert a temporary test result with conflicting status (DNF with positive score)
        reg = db.scalar(select(Registration).where(Registration.event_id == event_id))
        test_res = Result(
            event_id=event_id,
            registration_id=reg.id if reg else 1,
            raw_value=10.5,
            competition_status="DNF",  # Conflict!
            state="SUBMITTED",
        )
        db.add(test_res)
        db.commit()
        res_id = test_res.id

    try:
        report_res = client.get(f"/api/v1/ai/anomalies?event_id={event_id}", headers=teacher_headers)
        assert report_res.status_code == 200
        report = report_res.json()
        assert report["anomaly_count"] >= 1
        assert any(item["result_id"] == res_id and item["anomaly_level"] == "HIGH" for item in report["items"])
        item = next(item for item in report["items"] if item["result_id"] == res_id)
        assert "状态与成绩冲突" in item["issue_type"]
        assert "人工确认" in item["suggested_action"]
    finally:
        with SessionLocal() as db:
            row = db.get(Result, res_id)
            if row:
                db.delete(row)
                db.commit()


# ------------------------------------------------------------------------------
# 8. Full End-to-End Chat with Mocked Tool Calling & Audit Trail
# ------------------------------------------------------------------------------
def test_chat_flow_with_tool_calling_and_audit(client: TestClient, student_headers, dev_headers):
    # Register an active model config
    with SessionLocal() as db:
        cfg = AIModelConfig(
            provider_name="Test Chat Provider",
            provider_type="OPENAI_COMPATIBLE",
            base_url="https://mock.llm.com/v1",
            api_key_ciphertext=encrypt_api_key("sk-test-chat-key"),
            api_key_masked="sk-***key",
            model_name="test-chat-model",
            is_enabled=True,
            is_default=True,
        )
        db.add(cfg)
        db.commit()
        cfg_id = cfg.id

    try:
        # Mock LLM calling get_student_schedule tool, then interpreting it
        tool_call_resp = LLMResponse(
            content="",
            tool_calls=[{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "get_student_schedule",
                    "arguments": {},
                },
            }],
            token_usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
            model="test-chat-model",
            provider="OPENAI_COMPATIBLE",
        )
        followup_resp = LLMResponse(
            content="您好！查询到您的下一场比赛是【男子100米】初赛，检录时间为上午 08:30，请提前到达场地检录！",
            tool_calls=None,
            token_usage={"prompt_tokens": 80, "completion_tokens": 30, "total_tokens": 110},
            model="test-chat-model",
            provider="OPENAI_COMPATIBLE",
        )

        with patch("backend.app.ai.providers.openai_adapter.OpenAICompatibleAdapter.chat", side_effect=[tool_call_resp, followup_resp]):
            chat_res = client.post(
                "/api/v1/ai/chat",
                headers=student_headers,
                json={"message": "我下一场比赛是什么时候？"},
            )
            assert chat_res.status_code == 200, chat_res.text
            data = chat_res.json()
            assert "男子100米" in data["content"]
            assert data["tool_calls"] is not None
            assert any(t["name"] == "get_student_schedule" for t in data["tool_calls"])

        # Verify AI Audit Log was written
        audit_res = client.get("/api/v1/ai/audit-logs", headers=dev_headers)
        assert audit_res.status_code == 200
        logs = audit_res.json()
        assert len(logs) > 0
        assert any(l["action_type"] == "CHAT" for l in logs)

        # Verify AI Stats endpoint
        stats_res = client.get("/api/v1/ai/stats", headers=dev_headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["total_conversations"] >= 1
        assert stats["total_messages"] >= 1
    finally:
        with SessionLocal() as db:
            row = db.get(AIModelConfig, cfg_id)
            if row:
                db.delete(row)
                db.commit()
