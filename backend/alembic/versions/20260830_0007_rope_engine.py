"""add structured rope skipping lineups and result details

Revision ID: 20260830_0007
Revises: 20260827_0006
"""
from alembic import op
import sqlalchemy as sa


revision = "20260830_0007"
down_revision = "20260827_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "rope_lineup_members" not in tables:
        op.create_table(
            "rope_lineup_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
            sa.Column("college_team_id", sa.Integer(), sa.ForeignKey("college_teams.id", ondelete="CASCADE"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_roster.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False, default=1),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("event_id", "college_team_id", "student_id", name="uq_rope_lineup_event_team_student"),
            sa.CheckConstraint("role IN ('JUMPER', 'TURNER')", name="ck_rope_lineup_role"),
        )
        op.create_index("ix_rope_lineup_members_event_id", "rope_lineup_members", ["event_id"])
        op.create_index("ix_rope_lineup_members_college_team_id", "rope_lineup_members", ["college_team_id"])
        op.create_index("ix_rope_lineup_members_student_id", "rope_lineup_members", ["student_id"])
    if "rope_result_details" not in tables:
        op.create_table(
            "rope_result_details",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("result_id", sa.Integer(), sa.ForeignKey("results.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("individual_counts", sa.JSON(), nullable=True),
            sa.Column("completed_target", sa.Boolean(), nullable=True),
            sa.Column("elapsed_seconds", sa.Numeric(10, 2), nullable=True),
            sa.Column("completed_count", sa.Integer(), nullable=True),
            sa.Column("published_detail", sa.JSON(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_rope_result_details_result_id", "rope_result_details", ["result_id"], unique=True)


def downgrade() -> None:
    raise RuntimeError("该迁移包含跳绳阵容与结构化成绩数据，禁止自动降级以避免数据丢失")
