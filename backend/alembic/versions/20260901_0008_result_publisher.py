"""store the result publisher independently from the final reviewer

Revision ID: 20260901_0008
Revises: 20260830_0007
"""
from alembic import op
import sqlalchemy as sa


revision = "20260901_0008"
down_revision = "20260830_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_results"))
    columns = {column["name"] for column in sa.inspect(bind).get_columns("results")}
    if "publisher_id" not in columns:
        with op.batch_alter_table("results") as batch:
            batch.add_column(sa.Column("publisher_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_results_publisher_id", "users", ["publisher_id"], ["id"])
    bind.execute(
        sa.text(
            "UPDATE results SET publisher_id = finalized_by_id "
            "WHERE publisher_id IS NULL AND published_at IS NOT NULL"
        )
    )


def downgrade() -> None:
    raise RuntimeError("该迁移包含成绩发布人员审计数据，禁止自动降级以避免数据丢失")
