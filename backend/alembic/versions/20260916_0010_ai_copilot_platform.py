"""add ai copilot platform tables

Revision ID: 20260916_0010
Revises: 20260901_0009
"""
from alembic import op
import sqlalchemy as sa


revision = "20260916_0010"
down_revision = "20260901_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()

    # 1. ai_model_configs
    if "ai_model_configs" not in tables:
        op.create_table(
            "ai_model_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider_name", sa.String(length=128), nullable=False),
            sa.Column("provider_type", sa.String(length=32), nullable=False),
            sa.Column("base_url", sa.String(length=512), nullable=False),
            sa.Column("api_key_ciphertext", sa.Text(), nullable=False),
            sa.Column("api_key_masked", sa.String(length=64), nullable=False),
            sa.Column("model_name", sa.String(length=128), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=False, server_default="0.3"),
            sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2048"),
            sa.Column("timeout", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # 2. ai_conversations
    if "ai_conversations" not in tables:
        op.create_table(
            "ai_conversations",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("user_role", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False, server_default="新对话"),
            sa.Column("meet_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["meet_id"], ["sports_meets.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])

    # 3. ai_messages
    if "ai_messages" not in tables:
        op.create_table(
            "ai_messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("conversation_id", sa.String(length=64), nullable=False),
            sa.Column("role", sa.String(length=24), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("model_name", sa.String(length=128), nullable=True),
            sa.Column("provider_type", sa.String(length=32), nullable=True),
            sa.Column("tool_calls", sa.JSON(), nullable=True),
            sa.Column("tool_call_id", sa.String(length=64), nullable=True),
            sa.Column("token_usage", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])

    # 4. ai_tool_logs
    if "ai_tool_logs" not in tables:
        op.create_table(
            "ai_tool_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("conversation_id", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("tool_name", sa.String(length=64), nullable=False),
            sa.Column("arguments", sa.JSON(), nullable=True),
            sa.Column("result_summary", sa.Text(), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_tool_logs_conversation_id", "ai_tool_logs", ["conversation_id"])
        op.create_index("ix_ai_tool_logs_user_id", "ai_tool_logs", ["user_id"])
        op.create_index("ix_ai_tool_logs_tool_name", "ai_tool_logs", ["tool_name"])

    # 5. ai_audit_logs
    if "ai_audit_logs" not in tables:
        op.create_table(
            "ai_audit_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("conversation_id", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("user_role", sa.String(length=32), nullable=True),
            sa.Column("action_type", sa.String(length=48), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=True),
            sa.Column("model", sa.String(length=128), nullable=True),
            sa.Column("tool_name", sa.String(length=64), nullable=True),
            sa.Column("tool_arguments", sa.JSON(), nullable=True),
            sa.Column("tool_result_summary", sa.Text(), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("token_usage", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_audit_logs_conversation_id", "ai_audit_logs", ["conversation_id"])
        op.create_index("ix_ai_audit_logs_user_id", "ai_audit_logs", ["user_id"])
        op.create_index("ix_ai_audit_logs_action_type", "ai_audit_logs", ["action_type"])
        op.create_index("ix_ai_audit_logs_created_at", "ai_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_audit_logs")
    op.drop_table("ai_tool_logs")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("ai_model_configs")
