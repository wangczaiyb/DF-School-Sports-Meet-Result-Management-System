"""scope participant registrations to event rounds

Revision ID: 20260824_0004
Revises: 20260824_0003
"""
from alembic import op
import sqlalchemy as sa


revision = "20260824_0004"
down_revision = "20260824_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("registrations")}
    if "round_id" in columns:
        return
    event_rounds = sa.table(
        "event_rounds",
        sa.column("id", sa.Integer),
        sa.column("event_id", sa.Integer),
        sa.column("sequence", sa.Integer),
    )
    registrations = sa.table(
        "registrations",
        sa.column("id", sa.Integer),
        sa.column("event_id", sa.Integer),
        sa.column("round_id", sa.Integer),
    )
    with op.batch_alter_table("registrations", recreate="always") as batch:
        batch.drop_constraint("uq_registration_event_student", type_="unique")
        batch.drop_constraint("uq_registration_event_college_team", type_="unique")
        batch.add_column(sa.Column("round_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_registrations_round_id", "event_rounds", ["round_id"], ["id"])
        batch.create_index("ix_registrations_round_id", ["round_id"])
    connection = op.get_bind()
    for row in connection.execute(sa.select(registrations.c.id, registrations.c.event_id)):
        round_id = connection.execute(
            sa.select(event_rounds.c.id)
            .where(event_rounds.c.event_id == row.event_id)
            .order_by(event_rounds.c.sequence, event_rounds.c.id)
            .limit(1)
        ).scalar_one()
        connection.execute(registrations.update().where(registrations.c.id == row.id).values(round_id=round_id))
    with op.batch_alter_table("registrations", recreate="always") as batch:
        batch.alter_column("round_id", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_registration_round_student", ["event_id", "round_id", "student_id"])
        batch.create_unique_constraint("uq_registration_round_college_team", ["event_id", "round_id", "college_team_id"])


def downgrade() -> None:
    raise RuntimeError("该迁移包含多轮次参赛名单，禁止自动降级以避免数据丢失")
