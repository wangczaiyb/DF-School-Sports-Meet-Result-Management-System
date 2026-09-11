"""allow registrations for college teams

Revision ID: 20260824_0003
Revises: 20260824_0002
"""
from alembic import op
import sqlalchemy as sa


revision = "20260824_0003"
down_revision = "20260824_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("registrations")}
    if "college_team_id" in columns and columns["student_id"]["nullable"]:
        return
    with op.batch_alter_table("registrations", recreate="always") as batch:
        if "college_team_id" not in columns:
            batch.add_column(sa.Column("college_team_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_registrations_college_team_id", "college_teams", ["college_team_id"], ["id"])
            batch.create_index("ix_registrations_college_team_id", ["college_team_id"])
        batch.alter_column("student_id", existing_type=sa.Integer(), nullable=True)
        batch.create_unique_constraint("uq_registration_event_college_team", ["event_id", "college_team_id"])
        batch.create_check_constraint(
            "ck_registration_exactly_one_participant",
            "(student_id IS NOT NULL AND college_team_id IS NULL) OR (student_id IS NULL AND college_team_id IS NOT NULL)",
        )


def downgrade() -> None:
    raise RuntimeError("该迁移包含学院集体参赛数据，禁止自动降级以避免数据丢失")
