from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.identity import utcnow
from app.models.base import uuid_str


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint("status IN ('active','suspended','deleted')", name="ck_organizations_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("organization_id", "parent_department_id", "name", name="uq_departments_scope_name"),
        CheckConstraint("status IN ('active','archived')", name="ck_departments_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProjectSpace(Base):
    __tablename__ = "project_spaces"
    __table_args__ = (
        UniqueConstraint("organization_id", "department_id", "name", name="uq_project_spaces_scope_name"),
        CheckConstraint("visibility IN ('private','organization')", name="ck_project_spaces_visibility"),
        CheckConstraint("status IN ('active','archived')", name="ck_project_spaces_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private", server_default="private", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", "department_id", "project_space_id",
            name="uq_memberships_user_scope",
        ),
        CheckConstraint("space_type IN ('organization','department','project')", name="ck_memberships_space_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    project_space_id: Mapped[str | None] = mapped_column(ForeignKey("project_spaces.id", ondelete="CASCADE"), nullable=True)
    space_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", "department_id", "project_space_id",
            name="uq_role_assignments_user_scope",
        ),
        CheckConstraint("role IN ('owner','admin','member','viewer')", name="ck_role_assignments_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    project_space_id: Mapped[str | None] = mapped_column(ForeignKey("project_spaces.id", ondelete="CASCADE"), nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    granted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
