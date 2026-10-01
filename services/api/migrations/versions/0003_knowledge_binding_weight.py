"""knowledge binding weight

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29

说明：0002 用 `Base.metadata.create_all` 建表，其 DDL 取自**当前**模型，
因此全新库在 0002 之后可能已经有 `weight` 列。本迁移按「列存在则跳过」实现，
保证 `upgrade head` 在「全新库」与「已升级 0002 的老库」两种路径下都幂等。
"""

import sqlalchemy as sa
from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("knowledge_bindings")}
    if "weight" not in columns:
        op.add_column(
            "knowledge_bindings",
            sa.Column("weight", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("knowledge_bindings")}
    if "weight" in columns:
        op.drop_column("knowledge_bindings", "weight")
