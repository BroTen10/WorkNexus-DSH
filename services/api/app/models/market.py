"""插件市场治理实体（T-102 / T-103）。

  - `PluginWhitelistEntry`：企业白名单（插件 + 版本 + 兼容性声明 + 来源），T-103 增加版本锁定字段；
  - `PluginApprovalRequest`：安装/更新/启停的审批请求与决定（可追踪：请求人、决定人、时间、理由）。
"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_str
from app.models.identity import utcnow


class PluginWhitelistEntry(Base):
    __tablename__ = "plugin_whitelist_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "plugin_id", name="uq_plugin_whitelist_org_plugin"),
        CheckConstraint("status IN ('active','revoked')", name="ck_plugin_whitelist_status"),
        CheckConstraint(
            "source IN ('private-registry','official','local')",
            name="ck_plugin_whitelist_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plugin_id: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    dsh_compatibility: Mapped[str | None] = mapped_column(String(100), nullable=True)
    host_core_compatibility: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="private-registry",
                                        server_default="private-registry", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    approved_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # T-103 版本锁定：锁定后不允许自动升级
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    locked_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PluginApprovalRequest(Base):
    __tablename__ = "plugin_approval_requests"
    __table_args__ = (
        CheckConstraint(
            "action IN ('install','update','enable','disable')",
            name="ck_plugin_approval_action",
        ),
        CheckConstraint("status IN ('pending','approved','rejected')", name="ck_plugin_approval_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plugin_id: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
