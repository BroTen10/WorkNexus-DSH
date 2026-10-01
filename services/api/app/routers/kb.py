"""知识库控制面：连接（KnowledgeBase）与空间绑定（KnowledgeBinding）。

权限口径（P3-F09「管理员可配置 Provider、绑定空间、启停知识库」）：
  - 读：组织成员即可（`member` 及以上）；
  - 写：**至少 admin**——即「Host Core 矩阵允许 `kb.bind`」与「P3-F09 要求管理员」的交集；
    裁决记录见 `docs/知识库绑定_T-063.md`（控面比矩阵更严，矩阵本身不改）；
  - 未授权一律 404，不泄漏资源存在性（与 T-045 同口径）。

绑定范围只允许部门或项目空间之一（P3-F03），不存在会话级绑定；绑定变更写审计（§6.2 第 5 类）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Department, KnowledgeBase, KnowledgeBinding, ProjectSpace, User
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user
from app.services.audit import write_audit

router = APIRouter(prefix="/api/v1", tags=["knowledge"])

KNOWLEDGE_BASE_STATUSES = ("active", "disabled", "failed")


class KnowledgeBaseRequest(BaseModel):
    organizationId: str
    name: str = Field(min_length=1, max_length=200)
    providerType: str = Field(min_length=1, max_length=64)
    endpointUrl: str = Field(min_length=1, max_length=2000)
    configJson: str | None = Field(default=None, max_length=8000)


class KnowledgeBaseStatusRequest(BaseModel):
    status: str


class KnowledgeBindingRequest(BaseModel):
    knowledgeBaseId: str
    departmentId: str | None = None
    projectSpaceId: str | None = None
    weight: int = Field(default=0, ge=0, le=100)


def knowledge_base_body(row: KnowledgeBase) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "name": row.name,
        "providerType": row.provider_type,
        "endpointUrl": row.endpoint_url,
        "status": row.status,
        "configJson": row.config_json,
    }


def binding_body(row: KnowledgeBinding) -> dict[str, Any]:
    return {
        "id": row.id,
        "knowledgeBaseId": row.knowledge_base_id,
        "organizationId": row.organization_id,
        "departmentId": row.department_id,
        "projectSpaceId": row.project_space_id,
        "status": row.status,
        "enabled": row.status == "active",
        "weight": row.weight,
    }


def _require_endpoint(endpoint_url: str) -> str:
    if not (endpoint_url.startswith("http://") or endpoint_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="endpointUrl 必须是 http/https 绝对地址")
    return endpoint_url


def _require_scope(session: Session, organization_id: str, department_id: str | None,
                  project_space_id: str | None) -> None:
    if (department_id is None) == (project_space_id is None):
        raise HTTPException(status_code=400, detail="必须且只能指定部门或项目空间之一")
    if department_id is not None:
        department = session.get(Department, department_id)
        if department is None or department.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="部门不存在")
    if project_space_id is not None:
        space = session.get(ProjectSpace, project_space_id)
        if space is None or space.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="项目空间不存在")


@router.post("/knowledge-bases")
def create_knowledge_base(
    body: KnowledgeBaseRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "admin")
    _require_endpoint(body.endpointUrl)
    duplicate = session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.organization_id == body.organizationId,
            KnowledgeBase.name == body.name,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="知识库连接名称已存在")
    row = KnowledgeBase(
        organization_id=body.organizationId,
        name=body.name,
        provider_type=body.providerType,
        endpoint_url=body.endpointUrl,
        config_json=body.configJson,
    )
    session.add(row)
    session.flush()
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                action="kb.create", resource_type="knowledge_base", resource_id=row.id,
                summary=f"创建知识库连接 {body.name}")
    session.commit()
    return knowledge_base_body(row)


@router.get("/knowledge-bases")
def list_knowledge_bases(
    organization_id: str = Query(alias="organizationId"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    require_org_role(session, user, organization_id)
    rows = session.scalars(
        select(KnowledgeBase).where(KnowledgeBase.organization_id == organization_id)
    ).all()
    return [knowledge_base_body(row) for row in rows]


@router.patch("/knowledge-bases/{knowledge_base_id}")
def update_knowledge_base_status(
    knowledge_base_id: str,
    body: KnowledgeBaseStatusRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(KnowledgeBase, knowledge_base_id)
    if row is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    require_org_role(session, user, row.organization_id, "admin")
    if body.status not in KNOWLEDGE_BASE_STATUSES:
        raise HTTPException(status_code=400, detail="状态无效")
    row.status = body.status
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                action="kb.update", resource_type="knowledge_base", resource_id=row.id,
                summary=f"知识库 {row.name} 状态改为 {body.status}")
    session.commit()
    return knowledge_base_body(row)


@router.post("/knowledge-bindings")
def create_knowledge_binding(
    body: KnowledgeBindingRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    knowledge_base = session.get(KnowledgeBase, body.knowledgeBaseId)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    require_org_role(session, user, knowledge_base.organization_id, "admin")
    _require_scope(session, knowledge_base.organization_id, body.departmentId, body.projectSpaceId)
    duplicate = session.scalar(
        select(KnowledgeBinding).where(
            KnowledgeBinding.knowledge_base_id == knowledge_base.id,
            KnowledgeBinding.department_id == body.departmentId,
            KnowledgeBinding.project_space_id == body.projectSpaceId,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="该知识库已绑定到此空间")
    row = KnowledgeBinding(
        knowledge_base_id=knowledge_base.id,
        organization_id=knowledge_base.organization_id,
        department_id=body.departmentId,
        project_space_id=body.projectSpaceId,
        weight=body.weight,
        bound_by_user_id=user.id,
    )
    session.add(row)
    session.flush()
    scope_id = body.projectSpaceId or body.departmentId
    write_audit(session, user_id=user.id, organization_id=knowledge_base.organization_id,
                space_id=body.projectSpaceId, action="kb.bind",
                resource_type="knowledge_binding", resource_id=row.id,
                summary=f"绑定知识库 {knowledge_base.name} 到空间 {scope_id}")
    session.commit()
    return binding_body(row)


@router.get("/knowledge-bindings")
def list_knowledge_bindings(
    organization_id: str = Query(alias="organizationId"),
    department_id: str | None = Query(default=None, alias="departmentId"),
    project_space_id: str | None = Query(default=None, alias="projectSpaceId"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    require_org_role(session, user, organization_id)
    statement = select(KnowledgeBinding).where(KnowledgeBinding.organization_id == organization_id)
    if department_id is not None:
        statement = statement.where(KnowledgeBinding.department_id == department_id)
    if project_space_id is not None:
        statement = statement.where(KnowledgeBinding.project_space_id == project_space_id)
    rows = session.scalars(statement).all()
    return [binding_body(row) for row in rows]


@router.delete("/knowledge-bindings/{binding_id}")
def delete_knowledge_binding(
    binding_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(KnowledgeBinding, binding_id)
    if row is None:
        raise HTTPException(status_code=404, detail="绑定不存在")
    require_org_role(session, user, row.organization_id, "admin")
    session.delete(row)
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                space_id=row.project_space_id, action="kb.unbind",
                resource_type="knowledge_binding", resource_id=row.id,
                summary="解除知识库空间绑定")
    session.commit()
    return {"id": binding_id, "deleted": True}
