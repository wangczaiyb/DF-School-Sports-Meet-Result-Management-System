from __future__ import annotations

import json
import logging
import time
import uuid
from typing import AsyncIterator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Event, SportsMeet, User
from .gateway import LLMGateway
from .models import AIAuditLog, AIConversation, AIMessage
from .prompts import PromptManager
from .schemas import ChatRequest, ChatResponse
from .tools import tool_registry

logger = logging.getLogger(__name__)


def get_or_create_conversation(
    db: Session,
    user: User,
    conv_id: str | None = None,
    title: str | None = None,
    meet_id: int | None = None,
) -> AIConversation:
    """Find existing conversation for this user or create a new isolated conversation."""
    if conv_id:
        conv = db.scalar(
            select(AIConversation).where(
                AIConversation.id == conv_id,
                AIConversation.user_id == user.id,
            )
        )
        if conv:
            if meet_id and not conv.meet_id:
                conv.meet_id = meet_id
                db.commit()
            return conv

    # Create new conversation
    new_id = str(uuid.uuid4())
    conv = AIConversation(
        id=new_id,
        user_id=user.id,
        user_role=user.role,
        title=title or "新赛事协同对话",
        meet_id=meet_id,
    )
    db.add(conv)
    db.commit()
    return conv


def list_user_conversations(db: Session, user: User, limit: int = 50) -> list[dict]:
    """List conversation sessions belonging to the current user."""
    convs = list(
        db.scalars(
            select(AIConversation)
            .where(AIConversation.user_id == user.id)
            .order_by(AIConversation.updated_at.desc())
            .limit(limit)
        )
    )
    results = []
    for c in convs:
        msg_count = db.scalar(select(func.count(AIMessage.id)).where(AIMessage.conversation_id == c.id)) or 0
        results.append({
            "id": c.id,
            "title": c.title,
            "user_id": c.user_id,
            "user_role": c.user_role,
            "meet_id": c.meet_id,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "message_count": msg_count,
        })
    return results


def delete_user_conversation(db: Session, user: User, conv_id: str) -> bool:
    """Delete conversation and all its messages (strictly scoped by user_id)."""
    conv = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conv_id,
            AIConversation.user_id == user.id,
        )
    )
    if not conv:
        return False
    db.delete(conv)
    db.commit()
    return True


def get_conversation_messages(db: Session, user: User, conv_id: str) -> list[AIMessage]:
    """Fetch messages in a conversation (strictly scoped by user_id)."""
    conv = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conv_id,
            AIConversation.user_id == user.id,
        )
    )
    if not conv:
        return []
    return list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv_id)
            .order_by(AIMessage.id)
        )
    )


async def execute_chat(
    db: Session,
    user: User,
    req: ChatRequest,
) -> ChatResponse:
    """Execute complete chat completion with tool calling and audit trail."""
    start_time = time.perf_counter()
    conv = get_or_create_conversation(db, user, req.conversation_id, meet_id=req.meet_id)

    # 1. Title generation if first message
    if conv.title == "新赛事协同对话":
        first_title = req.message.strip()[:20]
        if len(req.message.strip()) > 20:
            first_title += "..."
        conv.title = first_title
        db.commit()

    # 2. Context assembly
    meet_name = None
    if req.meet_id:
        meet = db.get(SportsMeet, req.meet_id)
        if meet:
            meet_name = f"{meet.name}（{meet.edition}）"

    event_name = None
    if req.event_id:
        event = db.get(Event, req.event_id)
        if event:
            event_name = event.name

    system_prompt = PromptManager.build_system_prompt(
        user_role=user.role,
        user_display_name=user.display_name,
        meet_name=meet_name,
        event_name=event_name,
        page_context=req.page_context,
    )

    # 3. Save user message
    user_msg = AIMessage(
        conversation_id=conv.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    db.commit()

    # 4. Assemble history
    past_messages = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.id)
        )
    )

    # Convert to LLM format (limit last 12 messages for token efficiency)
    llm_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in past_messages[-12:]:
        if m.role == "user":
            llm_messages.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            msg_dict: dict = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            llm_messages.append(msg_dict)
        elif m.role == "tool":
            llm_messages.append({
                "role": "tool",
                "tool_call_id": m.tool_call_id or "",
                "content": m.content,
            })

    # 5. Tool definitions for this role
    tools = tool_registry.get_tool_definitions(user.role)

    # 6. Call LLM Gateway
    llm_resp, model_config = await LLMGateway.chat(db, llm_messages, tools=tools or None)

    total_tokens = dict(llm_resp.token_usage)
    executed_tools_summary = []

    # 7. Check if LLM requested tool calls
    if llm_resp.tool_calls:
        # Save assistant message with tool_calls
        assistant_tool_msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content=llm_resp.content or "",
            model_name=model_config.model_name,
            provider_type=model_config.provider_type,
            tool_calls=llm_resp.tool_calls,
            token_usage=llm_resp.token_usage,
        )
        db.add(assistant_tool_msg)
        db.commit()

        # Execute each tool
        llm_messages.append({
            "role": "assistant",
            "content": llm_resp.content or "",
            "tool_calls": llm_resp.tool_calls,
        })

        for tc in llm_resp.tool_calls:
            tc_id = tc.get("id", "")
            fn_meta = tc.get("function", {})
            fn_name = fn_meta.get("name", "")
            fn_args = fn_meta.get("arguments", {})

            # Auto inject meet_id / event_id from context if not provided
            if req.meet_id and "meet_id" not in fn_args and fn_name in ("get_events", "get_rankings", "get_event_statistics", "get_schedule", "get_pending_reviews"):
                fn_args["meet_id"] = req.meet_id
            if req.event_id and "event_id" not in fn_args and fn_name in ("get_results", "get_advancement", "check_result_anomalies", "get_schedule", "get_pending_reviews"):
                fn_args["event_id"] = req.event_id

            tool_result = await tool_registry.execute(
                tool_name=fn_name,
                arguments=fn_args,
                user=user,
                db=db,
                conversation_id=conv.id,
            )
            tool_result_str = json.dumps(tool_result, ensure_ascii=False)
            executed_tools_summary.append({"name": fn_name, "args": fn_args, "result": tool_result})

            # Save tool message in database
            tool_msg = AIMessage(
                conversation_id=conv.id,
                role="tool",
                content=tool_result_str,
                tool_call_id=tc_id,
            )
            db.add(tool_msg)
            db.commit()

            llm_messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_result_str,
            })

        # Follow-up LLM completion to interpret tool results
        follow_resp, _ = await LLMGateway.chat(db, llm_messages, tools=None)
        final_content = follow_resp.content
        total_tokens["prompt_tokens"] += follow_resp.token_usage.get("prompt_tokens", 0)
        total_tokens["completion_tokens"] += follow_resp.token_usage.get("completion_tokens", 0)
        total_tokens["total_tokens"] += follow_resp.token_usage.get("total_tokens", 0)
    else:
        final_content = llm_resp.content

    # Save final assistant message
    final_assistant_msg = AIMessage(
        conversation_id=conv.id,
        role="assistant",
        content=final_content,
        model_name=model_config.model_name,
        provider_type=model_config.provider_type,
        token_usage=total_tokens,
    )
    db.add(final_assistant_msg)
    conv.updated_at = func.now()
    db.commit()

    latency_total = int((time.perf_counter() - start_time) * 1000)

    # 8. Write AI Audit Trail
    audit_log = AIAuditLog(
        conversation_id=conv.id,
        user_id=user.id,
        user_role=user.role,
        action_type="CHAT",
        provider=model_config.provider_type,
        model=model_config.model_name,
        tool_name=",".join(t["name"] for t in executed_tools_summary) if executed_tools_summary else None,
        tool_arguments={"tools": executed_tools_summary} if executed_tools_summary else None,
        tool_result_summary=f"完成回答，包含 {len(executed_tools_summary)} 次工具调用",
        success=True,
        latency_ms=latency_total,
        token_usage=total_tokens,
    )
    db.add(audit_log)
    db.commit()

    return ChatResponse(
        conversation_id=conv.id,
        message_id=final_assistant_msg.id,
        content=final_content,
        tool_calls=executed_tools_summary or None,
        token_usage=total_tokens,
        model=model_config.model_name,
        provider=model_config.provider_type,
    )


async def execute_stream_chat(
    db: Session,
    user: User,
    req: ChatRequest,
) -> AsyncIterator[str]:
    """Execute streaming chat with SSE formatting."""
    start_time = time.perf_counter()
    conv = get_or_create_conversation(db, user, req.conversation_id, meet_id=req.meet_id)

    # First message title
    if conv.title == "新赛事协同对话":
        first_title = req.message.strip()[:20]
        if len(req.message.strip()) > 20:
            first_title += "..."
        conv.title = first_title
        db.commit()

    # Yield start event
    yield f"event: start\ndata: {json.dumps({'conversation_id': conv.id}, ensure_ascii=False)}\n\n"

    # Context assembly
    meet_name = None
    if req.meet_id:
        meet = db.get(SportsMeet, req.meet_id)
        if meet:
            meet_name = f"{meet.name}（{meet.edition}）"

    event_name = None
    if req.event_id:
        event = db.get(Event, req.event_id)
        if event:
            event_name = event.name

    system_prompt = PromptManager.build_system_prompt(
        user_role=user.role,
        user_display_name=user.display_name,
        meet_name=meet_name,
        event_name=event_name,
        page_context=req.page_context,
    )

    # Save user message
    user_msg = AIMessage(
        conversation_id=conv.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    db.commit()

    past_messages = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.id)
        )
    )

    llm_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in past_messages[-12:]:
        if m.role == "user":
            llm_messages.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            msg_dict: dict = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            llm_messages.append(msg_dict)
        elif m.role == "tool":
            llm_messages.append({
                "role": "tool",
                "tool_call_id": m.tool_call_id or "",
                "content": m.content,
            })

    tools = tool_registry.get_tool_definitions(user.role)

    try:
        stream_iter, model_config = await LLMGateway.stream_chat(db, llm_messages, tools=tools or None)
        collected_text = ""
        collected_tools: list[dict] | None = None
        usage_data = {}

        async for chunk in stream_iter:
            if chunk.delta_text:
                collected_text += chunk.delta_text
                yield f"event: token\ndata: {json.dumps({'text': chunk.delta_text}, ensure_ascii=False)}\n\n"
            if chunk.delta_tool_calls:
                collected_tools = chunk.delta_tool_calls
            if chunk.token_usage:
                usage_data.update(chunk.token_usage)

        # If tools were requested
        if collected_tools:
            executed_tools_summary = []
            for tc in collected_tools:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                fn_args = fn.get("arguments", {})

                if req.meet_id and "meet_id" not in fn_args and fn_name in ("get_events", "get_rankings", "get_event_statistics", "get_schedule", "get_pending_reviews"):
                    fn_args["meet_id"] = req.meet_id
                if req.event_id and "event_id" not in fn_args and fn_name in ("get_results", "get_advancement", "check_result_anomalies", "get_schedule", "get_pending_reviews"):
                    fn_args["event_id"] = req.event_id

                yield f"event: tool_start\ndata: {json.dumps({'tool_name': fn_name, 'arguments': fn_args}, ensure_ascii=False)}\n\n"

                tool_result = await tool_registry.execute(
                    tool_name=fn_name,
                    arguments=fn_args,
                    user=user,
                    db=db,
                    conversation_id=conv.id,
                )
                executed_tools_summary.append({"name": fn_name, "args": fn_args, "result": tool_result})
                yield f"event: tool_done\ndata: {json.dumps({'tool_name': fn_name, 'summary': str(tool_result)[:100]}, ensure_ascii=False)}\n\n"

                # Record tool msg
                tool_msg = AIMessage(
                    conversation_id=conv.id,
                    role="tool",
                    content=json.dumps(tool_result, ensure_ascii=False),
                    tool_call_id=tc.get("id", ""),
                )
                db.add(tool_msg)
                db.commit()

                llm_messages.append({
                    "role": "assistant",
                    "content": collected_text,
                    "tool_calls": collected_tools,
                })
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

            # Stream second turn for interpretation
            follow_stream, _ = await LLMGateway.stream_chat(db, llm_messages, tools=None)
            final_text = ""
            async for chunk in follow_stream:
                if chunk.delta_text:
                    final_text += chunk.delta_text
                    yield f"event: token\ndata: {json.dumps({'text': chunk.delta_text}, ensure_ascii=False)}\n\n"
                if chunk.token_usage:
                    usage_data.update(chunk.token_usage)
            collected_text = final_text

        # Save assistant message
        final_msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content=collected_text,
            model_name=model_config.model_name,
            provider_type=model_config.provider_type,
            token_usage=usage_data,
        )
        db.add(final_msg)
        db.commit()

        latency_total = int((time.perf_counter() - start_time) * 1000)

        # Audit log
        audit = AIAuditLog(
            conversation_id=conv.id,
            user_id=user.id,
            user_role=user.role,
            action_type="CHAT_STREAM",
            provider=model_config.provider_type,
            model=model_config.model_name,
            tool_name=",".join(t["name"] for t in collected_tools) if collected_tools else None,
            success=True,
            latency_ms=latency_total,
            token_usage=usage_data,
        )
        db.add(audit)
        db.commit()

        yield f"event: done\ndata: {json.dumps({'message_id': final_msg.id, 'content': collected_text, 'token_usage': usage_data}, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.exception(f"Stream chat failed: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
