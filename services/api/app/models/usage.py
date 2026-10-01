from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.identity import utcnow
from app.models.base import uuid_str
from datetime import timedelta


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        CheckConstraint(
            "source IN ('dsh_event','adapter_estimate','manual_import')",
            name="ck_usage_records_source",
        ),
        CheckConstraint("retention_days >= 1095", name="ck_usage_records_retention_min"),
        UniqueConstraint("usage_id", name="uq_usage_records_usage_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    usage_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    space_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plugin_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=1095, server_default="1095", nullable=False)
    retain_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: utcnow() + timedelta(days=1095), nullable=False
    )
    purge_approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purge_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BudgetPolicy(Base):
    __tablename__ = "budget_policies"
    __table_args__ = (
        CheckConstraint("scope IN ('organization','department','project','user')", name="ck_budget_policies_scope"),
        CheckConstraint("organization_id IS NOT NULL", name="ck_budget_policy_scope"),
        CheckConstraint("monthly_limit >= 0", name="ck_budget_policies_limit"),
        CheckConstraint("soft_threshold_percent <= hard_threshold_percent", name="ck_budget_policies_thresholds"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_space_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    monthly_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    soft_threshold_percent: Mapped[int] = mapped_column(Integer, default=80, server_default="80", nullable=False)
    hard_threshold_percent: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
