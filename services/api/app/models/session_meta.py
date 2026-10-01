from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.identity import utcnow
from app.models.base import uuid_str


class SessionMeta(Base):
    """企业会话元数据；不存储官方 prompt、output、transcript 或 messages。"""

    __tablename__ = "session_meta"
    __table_args__ = (
        UniqueConstraint("official_session_id", "organization_id", name="uq_session_meta_official_org"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    official_session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    project_space_id: Mapped[str | None] = mapped_column(ForeignKey("project_spaces.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
