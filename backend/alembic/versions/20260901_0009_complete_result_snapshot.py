"""complete the immutable public result snapshot

Revision ID: 20260901_0009
Revises: 20260901_0008
"""
from alembic import op
import sqlalchemy as sa


revision = "20260901_0009"
down_revision = "20260901_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_results"))
    columns = {column["name"] for column in sa.inspect(bind).get_columns("results")}
    if "published_competition_status" not in columns or "published_notes" not in columns:
        with op.batch_alter_table("results") as batch:
            if "published_competition_status" not in columns:
                batch.add_column(sa.Column("published_competition_status", sa.String(length=8), nullable=True))
            if "published_notes" not in columns:
                batch.add_column(sa.Column("published_notes", sa.String(length=255), nullable=True))
    bind.execute(
        sa.text(
            "UPDATE results SET "
            "published_competition_status = competition_status, published_notes = notes "
            "WHERE published_at IS NOT NULL AND published_competition_status IS NULL"
        )
    )


def downgrade() -> None:
    raise RuntimeError("该迁移包含已发布成绩快照数据，禁止自动降级以避免数据丢失")
