"""external service config

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-29

为 `ExternalService` 增加 `config_json`：承载外部服务的扩展参数（如私有源超时与回退源），
**不承载凭据值**（凭据只以引用形式放在 `auth_ref`）。

说明：0002 用 `Base.metadata.create_all` 建表，其 DDL 取自当前模型；本迁移按「列存在则跳过」实现，
对全新库与已升级库都幂等。
"""

import sqlalchemy as sa
from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("external_services")}


def upgrade() -> None:
    if "config_json" not in _columns():
        op.add_column("external_services", sa.Column("config_json", sa.Text(), nullable=True))


def downgrade() -> None:
    if "config_json" in _columns():
        op.drop_column("external_services", "config_json")
