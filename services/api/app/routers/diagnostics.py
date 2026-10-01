from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import RoleAssignment, User
from app.security.dependencies import get_current_user
from app.services.audit import write_audit
from app.services.report_store import ReportStore
from app.services.spaces import request_mode

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])

ALLOWED_FIELDS = {
    "runtimeVersion", "platform", "architecture", "profileValidation", "pluginStates",
    "errorType", "errorCode", "errorSummary", "timestamp", "anonymousInstallId",
}


class DiagnosticSettingsRequest(BaseModel):
    enabled: bool
    retentionDays: int = Field(default=30, ge=1, le=365)


def managed_organization_ids(session: Session, user: User) -> list[str]:
    rows = session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.role.in_(["owner", "admin"]),
        )
    ).all()
    return list(dict.fromkeys(row.organization_id for row in rows))


@router.post("/reports", status_code=202)
def receive_report(
    request: Request,
    body: dict[str, Any],
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if request_mode(request) == "personal":
        raise HTTPException(status_code=404, detail="个人模式不接受诊断上报")
    rejected = sorted(set(body) - ALLOWED_FIELDS)
    if rejected:
        raise HTTPException(status_code=422, detail={"rejectedFields": rejected})
    missing = sorted(ALLOWED_FIELDS - set(body))
    if missing:
        raise HTTPException(status_code=422, detail={"missingFields": missing})
    row = request.app.state.report_store.save(body)
    return {"reportId": row["reportId"], "status": "accepted"}


@router.get("/reports")
def list_reports(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    managed = managed_organization_ids(session, user)
    if not managed:
        write_audit(session, user_id=user.id, action="diagnostics.access_denied",
                    resource_type="diagnostics", result="denied", summary="非管理员查看诊断")
        session.commit()
        raise HTTPException(status_code=404, detail="组织不存在")
    store: ReportStore = request.app.state.report_store
    reports = store.list()
    write_audit(session, user_id=user.id, organization_id=managed[0], action="diagnostics.viewed",
                resource_type="diagnostics", summary=f"查看诊断 {len(reports)} 条")
    session.commit()
    return reports


@router.put("/settings")
def update_settings(
    body: DiagnosticSettingsRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if not managed_organization_ids(session, user):
        raise HTTPException(status_code=404, detail="组织不存在")
    settings = request.app.state.report_store.set_settings(body.enabled, body.retentionDays)
    write_audit(session, user_id=user.id, action="diagnostics.settings_updated",
                resource_type="diagnostics", summary=f"上报开关 {body.enabled}；留存 {settings['retentionDays']} 天")
    session.commit()
    return settings


@router.post("/cleanup")
def cleanup_reports(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if not managed_organization_ids(session, user):
        raise HTTPException(status_code=404, detail="组织不存在")
    removed = request.app.state.report_store.cleanup()
    write_audit(session, user_id=user.id, action="diagnostics.cleaned",
                resource_type="diagnostics", summary=f"清理过期诊断 {removed} 条")
    session.commit()
    return {"removed": removed}
