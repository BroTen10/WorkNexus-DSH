"""DocGraph Adapter 控制面（T-071 起步，T-074 扩展）。

原则（需求书 §4.4.2、T-009 §7）：
  - DocGraph 保持独立服务，控制面只做 Adapter：任务记录落在本地 `BackgroundJob`，
    不复制 DocGraph 的数据库/图谱/业务逻辑；
  - 提交只允许走 `POST /api/reviews/start` 对应的业务语义（由插件客户端调用远端），
    控制面不代理远端调用，也不使用内存态的 `build-graph-*`；
  - 权限：只有**空间成员/授权角色**可提交与查看；未授权一律 404，并写 `denied` 审计；
  - 审计：`docgraph.submit` / `docgraph.view` / `docgraph.cancel`（§6.2 第 6 类）。
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import BackgroundJob, ProjectSpace, RoleAssignment, UsageRecord, User
from app.models.identity import utcnow
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user
from app.services import permission as permission_service
from app.services.audit import write_audit
from app.services.spaces import visible_project_space_ids

router = APIRouter(prefix="/api/v1/docgraph", tags=["docgraph"])

# 权限动作 → 审计动作（§6.2 第 6 类只列提交/查看/取消，故读取动作记为 docgraph.view）
AUDIT_ACTION_FOR = {
    "docgraph.submit": "docgraph.submit",
    "docgraph.read": "docgraph.view",
}


class DocGraphTaskRequest(BaseModel):
    spaceId: str
    documentId: str = Field(min_length=1, max_length=200)
    contractId: str | None = Field(default=None, max_length=200)
    mode: Literal["analysis", "review"] = "review"


def job_body(row: BackgroundJob) -> dict[str, Any]:
    payload = json.loads(row.payload_json) if row.payload_json else {}
    result = json.loads(row.result_json) if row.result_json else None
    return {
        "jobId": row.id,
        "status": row.status,
        "jobType": row.job_type,
        "spaceId": payload.get("spaceId"),
        "documentId": payload.get("documentId"),
        "contractId": payload.get("contractId"),
        "mode": payload.get("mode"),
        "remoteTaskId": payload.get("remoteTaskId"),
        "submittedByUserId": row.submitted_by_user_id,
        "result": result,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def require_space_action(
    session: Session,
    user: User,
    space_id: str,
    action: str,
) -> ProjectSpace:
    """空间成员 + 动作权限双校验；失败写 `denied` 审计并返回 404（不泄漏存在性）。"""
    space = session.get(ProjectSpace, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="项目空间不存在")
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.organization_id == space.organization_id,
        )
    )
    allowed = (
        assignment is not None
        and permission_service.can({"role": assignment.role}, action)
        and (space_id in visible_project_space_ids(session, user, space.organization_id))
    )
    if not allowed:
        write_audit(session, user_id=user.id, organization_id=space.organization_id,
                    space_id=space_id, action=AUDIT_ACTION_FOR.get(action, "docgraph.view"),
                    resource_type="project_space",
                    resource_id=space_id, result="denied", summary="未授权访问 DocGraph 任务")
        session.commit()
        raise HTTPException(status_code=404, detail="项目空间不存在")
    return space


@router.post("/tasks", status_code=202)
def submit_task(
    body: DocGraphTaskRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    space = require_space_action(session, user, body.spaceId, "docgraph.submit")
    job = BackgroundJob(
        organization_id=space.organization_id,
        job_type=f"docgraph.{body.mode}",
        status="queued",
        payload_json=json.dumps({
            "spaceId": space.id,
            "documentId": body.documentId,
            "contractId": body.contractId,
            "mode": body.mode,
            "remoteTaskId": None,
        }, ensure_ascii=False),
        submitted_by_user_id=user.id,
    )
    session.add(job)
    session.flush()
    session.add(UsageRecord(
        usage_id=f"docgraph:{job.id}",
        organization_id=space.organization_id,
        space_id=space.id,
        user_id=user.id,
        plugin_id="docgraph",
        provider="docgraph",
        model=f"docgraph-{body.mode}",
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        estimated_cost=None,
        source="adapter_estimate",
    ))
    write_audit(session, user_id=user.id, organization_id=space.organization_id, space_id=space.id,
                action="docgraph.submit", resource_type="background_job", resource_id=job.id,
                summary=f"提交 DocGraph {body.mode} 任务（文档 {body.documentId}）")
    session.commit()
    return job_body(job)


@router.get("/tasks")
def list_jobs(
    space_id: str = Query(alias="spaceId"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    space = require_space_action(session, user, space_id, "docgraph.read")
    rows = session.scalars(
        select(BackgroundJob)
        .where(
            BackgroundJob.organization_id == space.organization_id,
            BackgroundJob.job_type.like("docgraph.%"),
        )
        .order_by(BackgroundJob.created_at.desc())
        .limit(limit)
    ).all()
    return [job_body(row) for row in rows if (json.loads(row.payload_json or "{}").get("spaceId") == space.id)]


def require_job_access(
    session: Session,
    user: User,
    job_id: str,
    action: str,
) -> BackgroundJob:
    job = session.get(BackgroundJob, job_id)
    if job is None or not job.job_type.startswith("docgraph."):
        raise HTTPException(status_code=404, detail="任务不存在")
    payload = json.loads(job.payload_json or "{}")
    space_id = payload.get("spaceId")
    if not isinstance(space_id, str):
        raise HTTPException(status_code=404, detail="任务不存在")
    require_space_action(session, user, space_id, action)
    return job


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    job = require_job_access(session, user, job_id, "docgraph.read")
    payload = json.loads(job.payload_json or "{}")
    write_audit(session, user_id=user.id, organization_id=job.organization_id,
                space_id=payload.get("spaceId"), action="docgraph.view",
                resource_type="background_job", resource_id=job.id,
                summary=f"查看 DocGraph 任务 {job.id}")
    session.commit()
    return job_body(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """平台侧取消：DocGraph 无取消端点（T-009），故只标记本地任务状态并显式说明。"""
    job = require_job_access(session, user, job_id, "docgraph.submit")
    payload = json.loads(job.payload_json or "{}")
    already_final = job.status in {"succeeded", "failed", "cancelled"}
    if not already_final:
        job.status = "cancelled"
        job.updated_at = utcnow()
        job.cancelled_by_user_id = user.id
    write_audit(session, user_id=user.id, organization_id=job.organization_id,
                space_id=payload.get("spaceId"), action="docgraph.cancel",
                resource_type="background_job", resource_id=job.id,
                summary=f"取消 DocGraph 任务 {job.id}")
    session.commit()
    return {
        **job_body(job),
        "remoteSupported": False,
        "detail": "docgraph-unsupported: 远端无取消端点（T-009 清单），仅平台侧标记取消",
    }
