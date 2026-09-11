"""add college team roster

Revision ID: 20260824_0002
Revises: 20260824_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260824_0002"
down_revision = "20260824_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("college_teams"):
        return
    op.create_table(
        "college_teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meet_id", sa.Integer(), sa.ForeignKey("sports_meets.id"), nullable=False),
        sa.Column("college", sa.String(length=128), nullable=False),
        sa.Column("team_name", sa.String(length=160), nullable=False),
        sa.Column("leader_name", sa.String(length=64), nullable=True),
        sa.Column("leader_phone", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("meet_id", "college", name="uq_college_team_meet_college"),
    )
    op.create_index("ix_college_teams_meet_id", "college_teams", ["meet_id"])
    op.create_index("ix_college_teams_college", "college_teams", ["college"])


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("college_teams"):
        op.drop_table("college_teams")
