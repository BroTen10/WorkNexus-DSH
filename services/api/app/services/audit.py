"""审计写入辅助；审计事件只追加，不在本模块提供更新或删除。"""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.models.identity import utcnow


AUDIT_ACTIONS = frozenset({
    # 登录 / 注册 / 验证码
    "auth.login", "auth.register", "auth.code_requested", "auth.login_failed",
    # 组织 / 部门 / 空间
    "organization.create", "organization.update", "organization.transfer_owner",
    "department.create", "department.update", "department.archive",
    "space.create", "space.update", "space.archive", "space.read",
    # 成员 / 角色
    "member.invite", "member.remove", "member.role_assign",
    # 插件
    "plugin.install", "plugin.update", "plugin.enable", "plugin.disable", "plugin.uninstall",
    "plugin.changed",
    # 知识库
    "kb.create", "kb.update", "kb.bind", "kb.unbind",
    # DocGraph
    "docgraph.submit", "docgraph.view", "docgraph.cancel", "docgraph.result",
    # ACP 后台自动化
    "acp.job.start", "acp.job.cancel", "acp.job.resume", "acp.job.close",
    "acp.permission.request",
    # 插件市场与治理
    "market.registry.update", "market.whitelist.update", "market.approval.request",
    "market.approval.decide", "market.version.lock", "market.install_requested",
    # 预算
    "budget.create", "budget.update",
    "usage.record",
    "diagnostics.viewed", "diagnostics.access_denied", "diagnostics.settings_updated", "diagnostics.cleaned",
    # 客户端升级
    "client.version.upgrade",
    # 审计治理
    "audit.export", "audit.purge_approved", "audit.corrected",
})


def write_audit(
    session: Session,
    *,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    organization_id: str | None = None,
    space_id: str | None = None,
    result: str = "success",
    device: str = "control-plane",
    summary: str,
    corrects_event_id: str | None = None,
) -> AuditEvent:
    if action not in AUDIT_ACTIONS:
        raise ValueError(f"audit action is not whitelisted: {action}")
    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        organization_id=organization_id,
        space_id=space_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        device=device,
        summary=summary[:200],
        corrects_event_id=corrects_event_id,
        retain_until=utcnow() + timedelta(days=1095),
    )
    session.add(event)
    session.flush()
    return event


def append_correction(
    session: Session,
    *,
    original: AuditEvent,
    user_id: str,
    summary: str,
    device: str = "control-plane",
) -> AuditEvent:
    return write_audit(
        session,
        user_id=user_id,
        organization_id=original.organization_id,
        space_id=original.space_id,
        action="audit.corrected",
        resource_type=original.resource_type,
        resource_id=original.resource_id,
        result="success",
        device=device,
        summary=summary,
        corrects_event_id=original.event_id,
    )
