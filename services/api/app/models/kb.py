from datetime import datetime

from datetime import timedelta

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.identity import utcnow
from app.models.base import uuid_str


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (CheckConstraint("status IN ('active','disabled','failed')", name="ck_knowledge_bases_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class KnowledgeBinding(Base):
    __tablename__ = "knowledge_bindings"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id", "department_id", "project_space_id",
            name="uq_knowledge_bindings_scope",
        ),
        CheckConstraint("status IN ('active','disabled')", name="ck_knowledge_bindings_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    project_space_id: Mapped[str | None] = mapped_column(ForeignKey("project_spaces.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    # 同一空间多知识库时的排序权重（越大越优先），T-063 裁决：全部生效并按权重排序
    weight: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    bound_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class KnowledgeRetrievalLog(Base):
    """检索日志（P3-F08）：记录请求、命中数、知识库、用户、空间、耗时。

    只追加：不提供更新/删除接口；**不保存查询正文与文档正文**，只保存查询摘要的
    哈希与长度（隐私边界同 §4.2.4 的只追加与留存规则）。
    """

    __tablename__ = "knowledge_retrieval_logs"
    __table_args__ = (
        CheckConstraint("hit_count >= 0", name="ck_knowledge_retrieval_logs_hit_count"),
        CheckConstraint("duration_ms >= 0", name="ck_knowledge_retrieval_logs_duration"),
        CheckConstraint("query_length >= 0", name="ck_knowledge_retrieval_logs_query_length"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    knowledge_base_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    query_length: Mapped[int] = mapped_column(Integer, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=1095, server_default="1095", nullable=False)
    retain_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: utcnow() + timedelta(days=1095), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
