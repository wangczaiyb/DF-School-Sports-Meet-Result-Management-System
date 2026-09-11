"""add college team members and volleyball match support

Revision ID: 20260826_0005
Revises: 20260824_0004
"""
from alembic import op
import sqlalchemy as sa


revision = "20260826_0005"
down_revision = "20260824_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "college_team_members" not in tables:
        op.create_table(
            "college_team_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("college_teams.id"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_roster.id"), nullable=False),
            sa.Column("role_title", sa.String(length=64), nullable=True),
            sa.Column("is_starter", sa.Boolean(), nullable=False, default=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("team_id", "student_id", name="uq_college_team_member"),
        )
        op.create_index("ix_college_team_members_team_id", "college_team_members", ["team_id"])
        op.create_index("ix_college_team_members_student_id", "college_team_members", ["student_id"])

    if "tournament_matches" in tables:
        match_cols = {col["name"] for col in inspector.get_columns("tournament_matches")}
        with op.batch_alter_table("tournament_matches") as batch:
            if "sets_detail" not in match_cols:
                batch.add_column(sa.Column("sets_detail", sa.JSON(), nullable=True))
            if "forfeit_team_id" not in match_cols:
                batch.add_column(sa.Column("forfeit_team_id", sa.Integer(), sa.ForeignKey("college_teams.id"), nullable=True))


def downgrade() -> None:
    raise RuntimeError("该迁移包含排球赛事及代表队成员数据，禁止自动降级以避免数据丢失")
