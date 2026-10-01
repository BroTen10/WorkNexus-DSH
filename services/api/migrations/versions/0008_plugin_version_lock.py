"""plugin version lock

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-29

白名单条目增加版本锁定字段（`locked` / `locked_version`），用于阻止自动升级。
按「列存在则跳过」实现，对全新库（0002 create_all 已含该列）与已升级库都幂等。
"""

import sqlalchemy as sa
from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABLE = "plugin_whitelist_entries"


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    columns = _columns()
    if "locked" not in columns:
        op.add_column(TABLE, sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    if "locked_version" not in columns:
        op.add_column(TABLE, sa.Column("locked_version", sa.String(64), nullable=True))


def downgrade() -> None:
    columns = _columns()
    if "locked_version" in columns:
        op.drop_column(TABLE, "locked_version")
    if "locked" in columns:
        op.drop_column(TABLE, "locked")
