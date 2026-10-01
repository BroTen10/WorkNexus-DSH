"""core entities

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29
"""

from alembic import op

from app.models.base import Base
import app.models  # noqa: F401


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
