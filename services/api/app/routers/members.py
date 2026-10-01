from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Membership, ProjectSpace, RoleAssignment, User
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user
from app.services.audit import write_audit

router = APIRouter(prefix="/api/v1", tags=["members"])


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member")


class RoleRequest(BaseModel):
    role: str
    user_id: str | None = None


def _validate_role(role: str) -> str:
    if role not in {"owner", "admin", "member", "viewer"}:
        raise HTTPException(status_code=400, detail="角色无效")
    return role


@router.post("/organizations/{organization_id}/members")
def invite_member(
    organization_id: str,
    body: InviteMemberRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organization_id, "admin")
    role = _validate_role(body.role)
    target = session.scalar(select(User).where(User.email == body.email))
    if target is None:
        raise HTTPException(status_code=404, detail="目标用户尚未注册")
    duplicate = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == target.id,
            RoleAssignment.organization_id == organization_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="成员已存在")
    session.add(Membership(
        user_id=target.id,
        organization_id=organization_id,
        space_type="organization",
    ))
    assignment = RoleAssignment(
        user_id=target.id,
        organization_id=organization_id,
        role=role,
        granted_by_user_id=user.id,
    )
    session.add(assignment)
    write_audit(session, user_id=user.id, organization_id=organization_id,
                action="member.invite", resource_type="user", resource_id=target.id,
                summary=f"邀请成员 {target.id} 为 {role}")
    session.commit()
    return {"userId": target.id, "email": target.email, "role": role}


@router.patch("/organizations/{organization_id}/members/{member_id}")
def assign_member_role(
    organization_id: str,
    member_id: str,
    body: RoleRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organization_id, "admin")
    role = _validate_role(body.role)
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == member_id,
            RoleAssignment.organization_id == organization_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    assignment.role = role
    write_audit(session, user_id=user.id, organization_id=organization_id,
                action="member.role_assign", resource_type="user", resource_id=member_id,
                summary=f"角色变更为 {role}")
    session.commit()
    return {"userId": member_id, "role": role}


@router.delete("/organizations/{organization_id}/members/{member_id}")
def remove_member(
    organization_id: str,
    member_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    require_org_role(session, user, organization_id, "admin")
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == member_id,
            RoleAssignment.organization_id == organization_id,
        )
    )
    membership = session.scalar(
        select(Membership).where(
            Membership.user_id == member_id,
            Membership.organization_id == organization_id,
        )
    )
    if assignment is None or membership is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    session.delete(assignment)
    session.delete(membership)
    write_audit(session, user_id=user.id, organization_id=organization_id,
                action="member.remove", resource_type="user", resource_id=member_id,
                summary="移除成员")
    session.commit()
    return {"status": "removed"}


@router.post("/project-spaces/{space_id}/members")
def grant_space_role(
    space_id: str,
    body: RoleRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    space = session.get(ProjectSpace, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="项目空间不存在")
    require_org_role(session, user, space.organization_id, "admin")
    role = _validate_role(body.role)
    target_id = body.user_id
    if target_id is None:
        raise HTTPException(status_code=400, detail="必须指定授权用户")
    target = session.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="目标用户不存在")
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == target_id,
            RoleAssignment.project_space_id == space_id,
        )
    )
    if assignment is not None:
        assignment.role = role
    else:
        session.add(RoleAssignment(
            user_id=target_id,
            organization_id=space.organization_id,
            project_space_id=space_id,
            role=role,
            granted_by_user_id=user.id,
        ))
    write_audit(session, user_id=user.id, organization_id=space.organization_id,
                space_id=space_id, action="member.role_assign", resource_type="project_space",
                resource_id=space_id, summary=f"空间角色设置为 {role}")
    session.commit()
    return {"userId": target_id, "spaceId": space_id, "role": role}
