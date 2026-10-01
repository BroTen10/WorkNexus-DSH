from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.identity import utcnow
from app.models.base import uuid_str
from datetime import timedelta


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("result IN ('success','failure','denied')", name="ck_audit_events_result"),
        CheckConstraint("retention_days >= 1095", name="ck_audit_events_retention_min"),
        UniqueConstraint("event_id", name="uq_audit_events_event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    space_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    device: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(200), nullable=False)
    corrects_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("audit_events.id", ondelete="RESTRICT"), nullable=True
    )
    retention_days: Mapped[int] = mapped_column(Integer, default=1095, server_default="1095", nullable=False)
    retain_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: utcnow() + timedelta(days=1095), nullable=False
    )
    purge_approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purge_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
