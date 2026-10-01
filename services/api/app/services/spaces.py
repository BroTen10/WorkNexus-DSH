"""项目空间可见性与默认拒绝。

owner 可见组织内全部空间；其他用户必须拥有显式项目空间 RoleAssignment。
个人模式永远返回空集合；未授权访问以 404 表达，不泄漏存在性。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProjectSpace, RoleAssignment, User


def request_mode(request) -> str:
    return (request.headers.get("X-WorkNexus-Mode") or "enterprise").lower()


def visible_project_space_ids(session: Session, user: User, organization_id: str) -> set[str]:
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.organization_id == organization_id,
        )
    )
    if assignment is None:
        return set()
    if assignment.role == "owner":
        rows = session.scalars(
            select(ProjectSpace.id).where(ProjectSpace.organization_id == organization_id)
        ).all()
        return set(rows)
    rows = session.scalars(
        select(RoleAssignment.project_space_id).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.organization_id == organization_id,
            RoleAssignment.project_space_id.is_not(None),
        )
    ).all()
    return set(rows)
