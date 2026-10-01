from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Department, Membership, Organization, ProjectSpace, RoleAssignment, User
from app.security.dependencies import get_current_user
from app.services.audit import write_audit
from app.services.spaces import request_mode, visible_project_space_ids

router = APIRouter(prefix="/api/v1", tags=["organizations"])

ROLE_RANK = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}


class OrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class DepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectSpaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class TransferOwnerRequest(BaseModel):
    user_id: str


def organization_body(row: Organization) -> dict[str, Any]:
    return {"id": row.id, "name": row.name, "ownerUserId": row.owner_user_id, "status": row.status}


def department_body(row: Department) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "parentDepartmentId": row.parent_department_id,
        "name": row.name,
        "status": row.status,
    }


def project_space_body(row: ProjectSpace) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "departmentId": row.department_id,
        "name": row.name,
        "description": row.description,
        "visibility": row.visibility,
        "status": row.status,
    }


def require_org_role(
    session: Session,
    user: User,
    organization_id: str,
    minimum: str = "member",
) -> RoleAssignment:
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.organization_id == organization_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    if ROLE_RANK[assignment.role] < ROLE_RANK[minimum]:
        raise HTTPException(status_code=404, detail="组织不存在")
    return assignment


@router.post("/organizations")
def create_organization(
    body: OrganizationRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    existing = session.scalar(select(Organization).where(Organization.name == body.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="组织名称已存在")
    org = Organization(name=body.name, owner_user_id=user.id)
    session.add(org)
    session.flush()
    session.add(Membership(
        user_id=user.id,
        organization_id=org.id,
        space_type="organization",
    ))
    session.add(RoleAssignment(
        user_id=user.id,
        organization_id=org.id,
        role="owner",
        granted_by_user_id=user.id,
    ))
    write_audit(session, user_id=user.id, organization_id=org.id, action="organization.create",
                resource_type="organization", resource_id=org.id, summary=f"创建组织 {body.name}")
    session.commit()
    return organization_body(org)


@router.get("/organizations")
def list_organizations(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    assignments = session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.project_space_id.is_(None),
        )
    ).all()
    org_ids = [item.organization_id for item in assignments]
    if not org_ids:
        return []
    rows = session.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()
    return [organization_body(row) for row in rows]


@router.get("/organizations/{organization_id}")
def get_organization(
    organization_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organization_id)
    row = session.get(Organization, organization_id)
    if row is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    return organization_body(row)


@router.patch("/organizations/{organization_id}")
def update_organization(
    organization_id: str,
    body: OrganizationRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organization_id, "owner")
    row = session.get(Organization, organization_id)
    if row is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    row.name = body.name
    write_audit(session, user_id=user.id, organization_id=row.id, action="organization.update",
                resource_type="organization", resource_id=row.id, summary=f"更新组织为 {body.name}")
    session.commit()
    return organization_body(row)


@router.get("/organizations/{organization_id}/members")
def list_members(
    organization_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    require_org_role(session, user, organization_id)
    rows = session.scalars(
        select(RoleAssignment).where(RoleAssignment.organization_id == organization_id)
    ).all()
    result = []
    for row in rows:
        member = session.get(User, row.user_id)
        result.append({
            "userId": row.user_id,
            "email": member.email if member else "",
            "role": row.role,
        })
    return result


@router.post("/organizations/{organization_id}/transfer-owner")
def transfer_owner(
    organization_id: str,
    body: TransferOwnerRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organization_id, "owner")
    org = session.get(Organization, organization_id)
    target = session.get(User, body.user_id)
    if org is None or target is None:
        raise HTTPException(status_code=404, detail="组织或目标用户不存在")
    previous = org.owner_user_id
    org.owner_user_id = target.id
    old_assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == previous,
            RoleAssignment.organization_id == org.id,
        )
    )
    if old_assignment is not None:
        old_assignment.role = "admin"
    target_assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == target.id,
            RoleAssignment.organization_id == org.id,
        )
    )
    if target_assignment is None:
        session.add(RoleAssignment(
            user_id=target.id,
            organization_id=org.id,
            role="owner",
            granted_by_user_id=user.id,
        ))
        session.add(Membership(
            user_id=target.id,
            organization_id=org.id,
            space_type="organization",
        ))
    else:
        target_assignment.role = "owner"
    write_audit(session, user_id=user.id, organization_id=org.id, action="organization.transfer_owner",
                resource_type="organization", resource_id=org.id, summary=f"组织所有权转移给 {target.id}")
    session.commit()
    return organization_body(org)


@router.post("/organizations/{organization_id}/departments")
def create_department(
    organization_id: str,
    body: DepartmentRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organization_id, "admin")
    duplicate = session.scalar(
        select(Department).where(
            Department.organization_id == organization_id,
            Department.parent_department_id.is_(None),
            Department.name == body.name,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="部门名称已存在")
    row = Department(organization_id=organization_id, name=body.name)
    session.add(row)
    session.flush()
    write_audit(session, user_id=user.id, organization_id=organization_id,
                action="department.create", resource_type="department", resource_id=row.id,
                summary=f"创建部门 {body.name}")
    session.commit()
    return department_body(row)


@router.get("/organizations/{organization_id}/departments")
def list_departments(
    organization_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    require_org_role(session, user, organization_id)
    rows = session.scalars(
        select(Department).where(Department.organization_id == organization_id)
    ).all()
    return [department_body(row) for row in rows]


@router.get("/departments/{department_id}")
def get_department(
    department_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(Department, department_id)
    if row is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    require_org_role(session, user, row.organization_id)
    return department_body(row)


@router.patch("/departments/{department_id}")
def update_department(
    department_id: str,
    body: DepartmentRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(Department, department_id)
    if row is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    require_org_role(session, user, row.organization_id, "admin")
    row.name = body.name
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                action="department.update", resource_type="department", resource_id=row.id,
                summary=f"更新部门为 {body.name}")
    session.commit()
    return department_body(row)


@router.delete("/departments/{department_id}")
def archive_department(
    department_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(Department, department_id)
    if row is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    require_org_role(session, user, row.organization_id, "admin")
    row.status = "archived"
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                action="department.archive", resource_type="department", resource_id=row.id,
                summary="归档部门")
    session.commit()
    return department_body(row)


@router.post("/departments/{department_id}/project-spaces")
def create_project_space(
    department_id: str,
    body: ProjectSpaceRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    department = session.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    require_org_role(session, user, department.organization_id, "admin")
    duplicate = session.scalar(
        select(ProjectSpace).where(
            ProjectSpace.department_id == department_id,
            ProjectSpace.name == body.name,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="项目空间名称已存在")
    row = ProjectSpace(
        organization_id=department.organization_id,
        department_id=department_id,
        name=body.name,
        description=body.description,
    )
    session.add(row)
    session.flush()
    write_audit(session, user_id=user.id, organization_id=department.organization_id,
                action="space.create", resource_type="project_space", resource_id=row.id,
                summary=f"创建项目空间 {body.name}")
    session.commit()
    return project_space_body(row)


@router.get("/organizations/{organization_id}/project-spaces")
def list_project_spaces(
    organization_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    if request_mode(request) == "personal":
        return []
    if session.get(Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.organization_id == organization_id,
        )
    )
    if assignment is None:
        return []
    visible = visible_project_space_ids(session, user, organization_id)
    rows = session.scalars(
        select(ProjectSpace).where(ProjectSpace.organization_id == organization_id)
    ).all()
    rows = [row for row in rows if row.id in visible]
    return [project_space_body(row) for row in rows]


@router.get("/project-spaces/{space_id}")
def get_project_space(
    space_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(ProjectSpace, space_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目空间不存在")
    if request_mode(request) == "personal" or space_id not in visible_project_space_ids(
        session, user, row.organization_id
    ):
        write_audit(session, user_id=user.id, organization_id=row.organization_id,
                    space_id=space_id, action="space.read", resource_type="project_space",
                    resource_id=space_id, result="denied", summary="未授权访问项目空间")
        session.commit()
        raise HTTPException(status_code=404, detail="项目空间不存在")
    return project_space_body(row)


@router.patch("/project-spaces/{space_id}")
def update_project_space(
    space_id: str,
    body: ProjectSpaceRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(ProjectSpace, space_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目空间不存在")
    require_org_role(session, user, row.organization_id, "admin")
    row.name = body.name
    row.description = body.description
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                action="space.update", resource_type="project_space", resource_id=row.id,
                summary=f"更新项目空间为 {body.name}")
    session.commit()
    return project_space_body(row)


@router.delete("/project-spaces/{space_id}")
def archive_project_space(
    space_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(ProjectSpace, space_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目空间不存在")
    require_org_role(session, user, row.organization_id, "admin")
    row.status = "archived"
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                action="space.archive", resource_type="project_space", resource_id=row.id,
                summary="归档项目空间")
    session.commit()
    return project_space_body(row)
