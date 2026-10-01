from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.identity import utcnow
from app.models.base import uuid_str


class PluginInstall(Base):
    __tablename__ = "plugin_installs"
    __table_args__ = (
        UniqueConstraint("organization_id", "plugin_id", name="uq_plugin_installs_org_plugin"),
        CheckConstraint(
            "state IN ('installed','enabled','disabled','failed','removed')",
            name="ck_plugin_installs_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    plugin_id: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="installed", server_default="installed", nullable=False)
    protected: Mapped[bool] = mapped_column(default=False, nullable=False)
    governance_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    governance_approval: Mapped[str | None] = mapped_column(String(16), nullable=True)
    installed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    @property
    def official_state(self) -> str:
        """官方 plugin-manager 是唯一权威；本列/属性只承载镜像值。"""
        return self.state

    @property
    def authoritative_source(self) -> str:
        """固定声明权威来源，防止企业库被误当作启停权威。"""
        return "official-plugin-manager"
