"""background job closed status

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-29

为后台任务（P6A）补充 `closed` 终态：ACP 会话「关闭」语义与「取消」不同，
因此扩展状态集合而不是复用 `cancelled` 冒充关闭。

说明：0002 用 `Base.metadata.create_all` 建表，其约束取自当前模型，
因此全新库里约束可能已经是新定义；本迁移按「存在则先删、缺失才建」实现，两条路径都幂等。
"""

from alembic import op

import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_background_jobs_status"
NEW_DEFINITION = "status IN ('queued','running','succeeded','failed','cancelled','closed')"
OLD_DEFINITION = "status IN ('queued','running','succeeded','failed','cancelled')"


def _has_constraint() -> bool:
    names = {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints("background_jobs")}
    return CONSTRAINT in names


def upgrade() -> None:
    if _has_constraint():
        op.drop_constraint(CONSTRAINT, "background_jobs", type_="check")
    op.create_check_constraint(CONSTRAINT, "background_jobs", NEW_DEFINITION)


def downgrade() -> None:
    if _has_constraint():
        op.drop_constraint(CONSTRAINT, "background_jobs", type_="check")
    op.create_check_constraint(CONSTRAINT, "background_jobs", OLD_DEFINITION)
