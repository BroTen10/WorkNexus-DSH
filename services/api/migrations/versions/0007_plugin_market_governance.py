"""plugin market governance

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-29

新增企业插件治理两张表：白名单条目与审批请求。
沿用 0002 的 `Base.metadata.create_all` 形态（只创建缺失表），对全新库与已升级库都幂等。
"""

from alembic import op

from app.models.base import Base
import app.models  # noqa: F401


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("plugin_approval_requests")
    op.drop_table("plugin_whitelist_entries")
