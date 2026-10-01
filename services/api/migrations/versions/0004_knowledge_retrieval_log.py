"""knowledge retrieval log

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29

说明：0002 用 `Base.metadata.create_all` 建表，本迁移沿用同一形态（只创建缺失表），
因此对全新库幂等；降级只删除本迁移引入的表。
"""

from alembic import op

from app.models.base import Base
import app.models  # noqa: F401


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("knowledge_retrieval_logs")
