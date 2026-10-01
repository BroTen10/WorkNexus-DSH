"""后台自动化任务（T-091，需求书 §4.6.1 功能 2/3、验收 2/3）。

语义：
  - 任务与**用户 / 空间 / 插件**关联（`payload_json` 保存 spaceId、pluginId、inputSummary）；
  - 生命周期：创建（queued）→ 取消（cancelled）/ 恢复（回 queued）/ 关闭（closed）；
  - 权限：空间成员 + `session.create`（写）/ `space.read`（读）；未授权一律 404 并写 `denied` 审计；
  - 状态变更写审计：`acp.job.start` / `acp.job.cancel` / `acp.job.resume` / `acp.job.close`；
  - 后台任务不阻塞主界面：所有接口都是短事务，不代理 ACP 运行时调用（执行由 T-090 适配层负责）。

裁决（T-091 派发卡默认值）：**恢复 = 重建会话并重放输入摘要**——因此 `resume` 只把任务重新置为
`queued`、累加 `resumes` 并保留 `inputSummary` 供调用方重放，不假装恢复了远端会话内存态。
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
from app.security.dependencies import get_current_user
from app.services import permission as permission_service
from app.services.audit import write_audit
from app.services.spaces import visible_project_space_ids

router = APIRouter(prefix="/api/v1", tags=["jobs"])

AUDIT_ACTION_FOR = {
    "session.create": "acp.job.start",
    "space.read": "acp.job.start",
}

RESUMABLE_STATUSES = {"queued", "running", "failed", "cancelled"}

ROLE_RANK = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}

# 企业侧工具策略（功能 4：权限请求必须有策略或管理员确认）
POLICY_AUTO_ALLOWED_TOOLS = frozenset({"fs.read", "search", "http.get"})
POLICY_ADMIN_REQUIRED_TOOLS = frozenset({"fs.write", "shell.exec", "http.post", "mcp.call"})


class JobRequest(BaseModel):
    spaceId: str
    kind: Literal["acp"] = "acp"
    pluginId: str | None = Field(default=None, max_length=200)
    inputSummary: str | None = Field(default=None, max_length=2000)


class PermissionRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=500)


def job_payload(row: BackgroundJob) -> dict[str, Any]:
    return json.loads(row.payload_json) if row.payload_json else {}


def job_body(row: BackgroundJob) -> dict[str, Any]:
    payload = job_payload(row)
    return {
        "id": row.id,
        "jobId": row.id,
        "status": row.status,
        "jobType": row.job_type,
        "kind": payload.get("kind", "acp"),
        "pluginId": payload.get("pluginId", "acp"),
        "spaceId": payload.get("spaceId"),
        "userId": row.submitted_by_user_id,
        "inputSummary": payload.get("inputSummary"),
        "resumes": payload.get("resumes", 0),
        "remoteSessionId": payload.get("remoteSessionId"),
        "result": json.loads(row.result_json) if row.result_json else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _context(session: Session, user: User, space: ProjectSpace) -> RoleAssignment | None:
    return session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.organization_id == space.organization_id,
        )
    )


def require_space(session: Session, user: User, space_id: str, action: str) -> ProjectSpace:
    space = session.get(ProjectSpace, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="项目空间不存在")
    assignment = _context(session, user, space)
    allowed = (
        assignment is not None
        and permission_service.can({"role": assignment.role}, action)
        and space.id in visible_project_space_ids(session, user, space.organization_id)
    )
    if not allowed:
        write_audit(session, user_id=user.id, organization_id=space.organization_id,
                    space_id=space_id, action=AUDIT_ACTION_FOR.get(action, "acp.job.start"),
                    resource_type="project_space", resource_id=space_id, result="denied",
                    summary="未授权访问后台任务")
        session.commit()
        raise HTTPException(status_code=404, detail="项目空间不存在")
    return space


def require_job(session: Session, user: User, job_id: str, action: str) -> BackgroundJob:
    row = session.get(BackgroundJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    space_id = job_payload(row).get("spaceId")
    if not isinstance(space_id, str):
        raise HTTPException(status_code=404, detail="任务不存在")
    require_space(session, user, space_id, action)
    return row


def _touch(row: BackgroundJob, payload: dict[str, Any]) -> None:
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.updated_at = utcnow()


@router.post("/jobs")
def create_job(
    body: JobRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    space = require_space(session, user, body.spaceId, "session.create")
    row = BackgroundJob(
        organization_id=space.organization_id,
        job_type=f"{body.kind}.background",
        status="queued",
        payload_json=json.dumps({
            "kind": body.kind,
            "pluginId": body.pluginId or body.kind,
            "spaceId": space.id,
            "inputSummary": body.inputSummary,
            "resumes": 0,
            "remoteSessionId": None,
        }, ensure_ascii=False),
        submitted_by_user_id=user.id,
    )
    session.add(row)
    session.flush()
    # ACP 会话进入用量体系（功能 5）：真实 token 由适配层 usage 钩子上报，这里留空不猜
    session.add(UsageRecord(
        usage_id=f"acp:{row.id}",
        organization_id=space.organization_id,
        space_id=space.id,
        user_id=user.id,
        plugin_id="acp",
        provider="acp",
        model="acp-session",
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        estimated_cost=None,
        source="adapter_estimate",
    ))
    write_audit(session, user_id=user.id, organization_id=space.organization_id, space_id=space.id,
                action="acp.job.start", resource_type="background_job", resource_id=row.id,
                summary=f"创建后台任务（{body.kind}）")
    session.commit()
    return job_body(row)


@router.get("/jobs")
def list_jobs(
    space_id: str | None = Query(default=None, alias="spaceId"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    assignments = session.scalars(
        select(RoleAssignment).where(RoleAssignment.user_id == user.id)
    ).all()
    organization_ids = {item.organization_id for item in assignments}
    if not organization_ids:
        return []
    rows = session.scalars(
        select(BackgroundJob)
        .where(BackgroundJob.organization_id.in_(organization_ids))
        .order_by(BackgroundJob.created_at.desc())
        .limit(limit)
    ).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        payload = job_payload(row)
        row_space = payload.get("spaceId")
        if not isinstance(row_space, str):
            continue
        if space_id is not None and row_space != space_id:
            continue
        if row_space not in visible_project_space_ids(session, user, row.organization_id):
            continue
        result.append(job_body(row))
    return result


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """查看单个后台任务（短事务，不代理 ACP 运行时）。"""
    row = require_job(session, user, job_id, "space.read")
    return job_body(row)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = require_job(session, user, job_id, "session.create")
    payload = job_payload(row)
    if row.status not in {"cancelled", "closed"}:
        row.status = "cancelled"
        row.cancelled_by_user_id = user.id
        _touch(row, payload)
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                space_id=payload.get("spaceId"), action="acp.job.cancel",
                resource_type="background_job", resource_id=row.id,
                summary=f"取消后台任务 {row.id}")
    session.commit()
    return job_body(row)


@router.post("/jobs/{job_id}/resume")
def resume_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = require_job(session, user, job_id, "session.create")
    if row.status not in RESUMABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"任务状态 {row.status} 不可恢复")
    payload = job_payload(row)
    payload["resumes"] = int(payload.get("resumes", 0)) + 1
    row.status = "queued"
    row.updated_at = utcnow()
    _touch(row, payload)
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                space_id=payload.get("spaceId"), action="acp.job.resume",
                resource_type="background_job", resource_id=row.id,
                summary=f"恢复后台任务 {row.id}（重放输入摘要）")
    session.commit()
    return job_body(row)


@router.post("/jobs/{job_id}/close")
def close_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = require_job(session, user, job_id, "session.create")
    payload = job_payload(row)
    already_closed = row.status == "closed"
    if not already_closed:
        row.status = "closed"
        _touch(row, payload)
        write_audit(session, user_id=user.id, organization_id=row.organization_id,
                    space_id=payload.get("spaceId"), action="acp.job.close",
                    resource_type="background_job", resource_id=row.id,
                    summary=f"关闭后台任务 {row.id}")
        session.commit()
    return {**job_body(row), "alreadyClosed": already_closed}


@router.post("/jobs/{job_id}/permission-request")
def request_permission(
    job_id: str,
    body: PermissionRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """ACP 权限请求：企业侧策略或管理员确认（§4.6.1 功能 4）。

    判定顺序（fail closed）：
      1. 工具在白名单内 → 策略自动放行（`decidedBy=policy`）；
      2. 工具属于需管理员确认（写类）→ `admin` / `owner` 视为管理员确认通过，其余角色 403；
      3. 其余未知工具 → 403（策略默认拒绝）。
    """
    row = require_job(session, user, job_id, "session.create")
    payload = job_payload(row)
    space = session.get(ProjectSpace, payload.get("spaceId")) if isinstance(payload.get("spaceId"), str) else None
    assignment = _context(session, user, space) if space is not None else None
    role = assignment.role if assignment is not None else "viewer"
    is_admin = ROLE_RANK.get(role, 0) >= ROLE_RANK["admin"]

    if body.tool in POLICY_AUTO_ALLOWED_TOOLS:
        decision, decided_by, reason = "allowed", "policy", "policy.auto_allowed"
    elif body.tool in POLICY_ADMIN_REQUIRED_TOOLS and is_admin:
        decision, decided_by, reason = "allowed", "admin", "admin.confirmed"
    elif body.tool in POLICY_ADMIN_REQUIRED_TOOLS:
        decision, decided_by, reason = "denied", "policy", "requires_admin_approval"
    else:
        decision, decided_by, reason = "denied", "policy", "policy.default_deny"

    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                space_id=payload.get("spaceId"), action="acp.permission.request",
                resource_type="background_job", resource_id=row.id,
                result="success" if decision == "allowed" else "denied",
                summary=f"工具 {body.tool} → {decision}（{reason}）")
    session.commit()

    if decision != "allowed":
        raise HTTPException(status_code=403, detail={
            "reason": reason,
            "tool": body.tool,
            "decision": decision,
            "decidedBy": decided_by,
        })
    return {
        "jobId": row.id,
        "tool": body.tool,
        "decision": decision,
        "decidedBy": decided_by,
        "reason": reason,
    }
