"""add table tennis singles and rubber support to tournament matches

Revision ID: 20260827_0006
Revises: 20260826_0005
"""
from alembic import op
import sqlalchemy as sa


revision = "20260827_0006"
down_revision = "20260826_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "tournament_matches" in tables:
        match_cols = {col["name"] for col in inspector.get_columns("tournament_matches")}
        with op.batch_alter_table("tournament_matches") as batch:
            if "home_student_id" not in match_cols:
                batch.add_column(sa.Column("home_student_id", sa.Integer(), sa.ForeignKey("student_roster.id"), nullable=True))
            if "away_student_id" not in match_cols:
                batch.add_column(sa.Column("away_student_id", sa.Integer(), sa.ForeignKey("student_roster.id"), nullable=True))
            if "winner_student_id" not in match_cols:
                batch.add_column(sa.Column("winner_student_id", sa.Integer(), sa.ForeignKey("student_roster.id"), nullable=True))
            if "loser_student_id" not in match_cols:
                batch.add_column(sa.Column("loser_student_id", sa.Integer(), sa.ForeignKey("student_roster.id"), nullable=True))
            if "best_of" not in match_cols:
                batch.add_column(sa.Column("best_of", sa.Integer(), nullable=True, default=3))
            if "team_rubber_detail" not in match_cols:
                batch.add_column(sa.Column("team_rubber_detail", sa.JSON(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("该迁移包含乒乓球赛制核心数据，禁止自动降级以避免数据丢失")
