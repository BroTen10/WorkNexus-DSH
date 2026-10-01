"""插件白名单与安装审批（T-102，需求书 P6B-F02/F03、§3.5）。

口径：
  - **企业模式**：未通过白名单的插件不能安装（403 `not_whitelisted`）；
  - **个人模式**：不强制企业白名单，只记录一次「可疑安装」审计（§3.5）；
  - 审批可追踪：请求人 / 决定人 / 时间 / 理由全部落在 `plugin_approval_requests` 并写审计；
  - 治理**不动官方流程**：控制面只给出 allow/deny 与审计，实际安装仍由官方插件管理器执行。
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import PluginApprovalRequest, PluginWhitelistEntry, RoleAssignment, User
from app.models.identity import utcnow
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user
from app.services.audit import write_audit
from app.services import plugin_policy
from app.services.spaces import request_mode

router = APIRouter(prefix="/api/v1/market", tags=["market"])

APPROVAL_ACTIONS = ("install", "update", "enable", "disable")


class WhitelistRequest(BaseModel):
    organizationId: str
    pluginId: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=64)
    dshCompatibility: str | None = Field(default=None, max_length=100)
    hostCoreCompatibility: str | None = Field(default=None, max_length=100)
    source: Literal["private-registry", "official", "local"] = "private-registry"


class ApprovalRequest(BaseModel):
    organizationId: str
    pluginId: str = Field(min_length=1, max_length=200)
    version: str = Field(default="*", max_length=64)
    action: Literal["install", "update", "enable", "disable"] = "install"


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=500)


class InstallRequest(BaseModel):
    pluginId: str = Field(min_length=1, max_length=200)
    version: str | None = Field(default=None, max_length=64)
    organizationId: str | None = None
    mode: Literal["enterprise", "personal"] | None = None


class VersionLockRequest(BaseModel):
    organizationId: str
    version: str | None = Field(default=None, max_length=64)


class UpgradeRequest(BaseModel):
    organizationId: str
    targetVersion: str | None = Field(default=None, max_length=64)


def whitelist_body(row: PluginWhitelistEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "pluginId": row.plugin_id,
        "version": row.version,
        "dshCompatibility": row.dsh_compatibility,
        "hostCoreCompatibility": row.host_core_compatibility,
        "source": row.source,
        "status": row.status,
        "approvedByUserId": row.approved_by_user_id,
        "locked": row.locked,
        "lockedVersion": row.locked_version,
    }


def approval_body(row: PluginApprovalRequest) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "pluginId": row.plugin_id,
        "version": row.version,
        "action": row.action,
        "status": row.status,
        "requestedByUserId": row.requested_by_user_id,
        "decidedByUserId": row.decided_by_user_id,
        "reason": row.reason,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "decidedAt": row.decided_at.isoformat() if row.decided_at else None,
    }


def _first_organization(session: Session, user: User) -> str | None:
    assignment = session.scalar(
        select(RoleAssignment).where(RoleAssignment.user_id == user.id)
    )
    return assignment.organization_id if assignment is not None else None


@router.post("/whitelist")
def add_whitelist_entry(
    body: WhitelistRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "admin")
    problems = plugin_policy.validate_declaration(body.dshCompatibility, body.hostCoreCompatibility)
    if problems:
        raise HTTPException(status_code=422, detail={
            "reason": "invalid_compatibility_declaration",
            "problems": problems,
            "detail": plugin_policy.summarize(problems),
        })
    compatibility = plugin_policy.check_compatibility(
        dsh_compatibility=body.dshCompatibility,
        host_core_compatibility=body.hostCoreCompatibility,
    )
    if not compatibility["ok"]:
        raise HTTPException(status_code=422, detail={
            "reason": "incompatible",
            "problems": compatibility["problems"],
            "detail": plugin_policy.summarize(compatibility["problems"]),
        })
    row = session.scalar(
        select(PluginWhitelistEntry).where(
            PluginWhitelistEntry.organization_id == body.organizationId,
            PluginWhitelistEntry.plugin_id == body.pluginId,
        )
    )
    if row is None:
        row = PluginWhitelistEntry(
            organization_id=body.organizationId,
            plugin_id=body.pluginId,
            version=body.version,
            dsh_compatibility=body.dshCompatibility,
            host_core_compatibility=body.hostCoreCompatibility,
            source=body.source,
            approved_by_user_id=user.id,
        )
        session.add(row)
    else:
        row.version = body.version
        row.dsh_compatibility = body.dshCompatibility
        row.host_core_compatibility = body.hostCoreCompatibility
        row.source = body.source
        row.status = "active"
        row.approved_by_user_id = user.id
    session.flush()
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                action="market.whitelist.update", resource_type="plugin", resource_id=row.plugin_id,
                summary=f"白名单批准 {body.pluginId}@{body.version}")
    session.commit()
    return whitelist_body(row)


@router.get("/whitelist")
def list_whitelist(
    organization_id: str = Query(alias="organizationId"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    require_org_role(session, user, organization_id)
    rows = session.scalars(
        select(PluginWhitelistEntry).where(PluginWhitelistEntry.organization_id == organization_id)
    ).all()
    return [whitelist_body(row) for row in rows]


@router.post("/approvals")
def request_approval(
    body: ApprovalRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "admin")
    row = PluginApprovalRequest(
        organization_id=body.organizationId,
        plugin_id=body.pluginId,
        version=body.version,
        action=body.action,
        requested_by_user_id=user.id,
    )
    session.add(row)
    session.flush()
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                action="market.approval.request", resource_type="plugin", resource_id=body.pluginId,
                summary=f"请求审批 {body.action} {body.pluginId}@{body.version}")
    session.commit()
    return approval_body(row)


@router.post("/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(PluginApprovalRequest, approval_id)
    if row is None:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    require_org_role(session, user, row.organization_id, "admin")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"审批已{dict(pending='待处理',approved='通过',rejected='拒绝')[row.status]}")
    row.status = body.decision
    row.decided_by_user_id = user.id
    row.reason = body.reason
    row.decided_at = utcnow()
    session.flush()
    if body.decision == "approved":
        existing = session.scalar(
            select(PluginWhitelistEntry).where(
                PluginWhitelistEntry.organization_id == row.organization_id,
                PluginWhitelistEntry.plugin_id == row.plugin_id,
            )
        )
        if existing is None:
            session.add(PluginWhitelistEntry(
                organization_id=row.organization_id,
                plugin_id=row.plugin_id,
                version=row.version,
                source="private-registry",
                approved_by_user_id=user.id,
            ))
    write_audit(session, user_id=user.id, organization_id=row.organization_id,
                action="market.approval.decide", resource_type="plugin", resource_id=row.plugin_id,
                result="success" if body.decision == "approved" else "denied",
                summary=f"审批 {body.decision}：{row.action} {row.plugin_id}@{row.version}")
    session.commit()
    return approval_body(row)


@router.get("/approvals")
def list_approvals(
    organization_id: str = Query(alias="organizationId"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    require_org_role(session, user, organization_id)
    rows = session.scalars(
        select(PluginApprovalRequest).where(PluginApprovalRequest.organization_id == organization_id)
    ).all()
    return [approval_body(row) for row in rows]


@router.post("/install")
def request_install(
    body: InstallRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """企业模式强制白名单；个人模式只记录可疑安装（§3.5）。实际安装由官方管理器执行。"""
    mode = body.mode or request_mode(request)
    organization_id = body.organizationId or _first_organization(session, user)

    if mode == "personal":
        write_audit(session, user_id=user.id, organization_id=organization_id,
                    action="market.install_requested", resource_type="plugin", resource_id=body.pluginId,
                    summary=f"个人模式安装请求（仅记录）：{body.pluginId}")
        session.commit()
        return {
            "pluginId": body.pluginId,
            "mode": "personal",
            "enforced": False,
            "detail": "个人模式不强制企业白名单，仅记录安装请求",
        }

    entry = None
    if organization_id is not None:
        entry = session.scalar(
            select(PluginWhitelistEntry).where(
                PluginWhitelistEntry.organization_id == organization_id,
                PluginWhitelistEntry.plugin_id == body.pluginId,
                PluginWhitelistEntry.status == "active",
            )
        )
    if entry is None:
        write_audit(session, user_id=user.id, organization_id=organization_id,
                    action="plugin.install", resource_type="plugin", resource_id=body.pluginId,
                    result="denied", summary=f"未通过白名单：{body.pluginId}")
        session.commit()
        raise HTTPException(status_code=403, detail={
            "reason": "not_whitelisted",
            "pluginId": body.pluginId,
            "mode": mode,
        })

    write_audit(session, user_id=user.id, organization_id=organization_id,
                action="plugin.install", resource_type="plugin", resource_id=body.pluginId,
                summary=f"白名单安装通过：{body.pluginId}@{entry.version}")
    session.commit()
    return {
        "pluginId": body.pluginId,
        "mode": "enterprise",
        "enforced": True,
        "version": entry.version,
        "source": entry.source,
        "approvedByUserId": entry.approved_by_user_id,
        "delegatedTo": "@deepseek-ai/dsh-plugin-manager",
    }


@router.post("/plugins/{plugin_id}/lock")
def lock_plugin_version(
    plugin_id: str,
    body: VersionLockRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "admin")
    row = session.scalar(
        select(PluginWhitelistEntry).where(
            PluginWhitelistEntry.organization_id == body.organizationId,
            PluginWhitelistEntry.plugin_id == plugin_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="插件不在白名单内")
    row.locked = True
    row.locked_version = body.version or row.version
    session.flush()
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                action="market.version.lock", resource_type="plugin", resource_id=plugin_id,
                summary=f"锁定插件版本 {plugin_id}@{row.locked_version}")
    session.commit()
    return whitelist_body(row)


@router.post("/plugins/{plugin_id}/upgrade")
def request_upgrade(
    plugin_id: str,
    body: UpgradeRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "admin")
    row = session.scalar(
        select(PluginWhitelistEntry).where(
            PluginWhitelistEntry.organization_id == body.organizationId,
            PluginWhitelistEntry.plugin_id == plugin_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="插件不在白名单内")
    target = body.targetVersion or row.version
    decision = plugin_policy.upgrade_allowed(
        locked=row.locked, target_version=target, locked_version=row.locked_version
    )
    if not decision["allowed"]:
        raise HTTPException(status_code=409, detail={
            "reason": decision["reason"],
            "detail": decision["detail"],
            "pluginId": plugin_id,
            "lockedVersion": row.locked_version,
        })
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                action="plugin.update", resource_type="plugin", resource_id=plugin_id,
                summary=f"允许升级 {plugin_id} → {target}")
    session.commit()
    return {
        "pluginId": plugin_id,
        "currentVersion": row.version,
        "targetVersion": target,
        "delegatedTo": "@deepseek-ai/dsh-plugin-manager",
    }
