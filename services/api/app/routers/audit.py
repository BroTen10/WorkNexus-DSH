from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import AuditEvent, RoleAssignment, User
from app.models.identity import as_utc, utcnow
from app.security.dependencies import get_current_user
from app.services.audit import append_correction, write_audit

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class CorrectionRequest(BaseModel):
    original_event_id: str
    summary: str = Field(min_length=1, max_length=200)


class PurgeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    to: datetime | None = None


class AuditEventRequest(BaseModel):
    userId: str
    organizationId: str | None = None
    spaceId: str | None = None
    action: str
    resourceType: str
    resourceId: str | None = None
    result: str = "success"
    device: str = "control-plane"
    summary: str


def managed_organization_ids(session: Session, user: User) -> list[str]:
    rows = session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.role.in_(["owner", "admin"]),
        )
    ).all()
    return list(dict.fromkeys(row.organization_id for row in rows))


def owner_organization_ids(session: Session, user: User) -> list[str]:
    rows = session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.role == "owner",
        )
    ).all()
    return list(dict.fromkeys(row.organization_id for row in rows))


def audit_body(row: AuditEvent) -> dict[str, Any]:
    return {
        "eventId": row.event_id,
        "timestamp": as_utc(row.timestamp).isoformat(),
        "userId": row.user_id,
        "organizationId": row.organization_id,
        "spaceId": row.space_id,
        "action": row.action,
        "resourceType": row.resource_type,
        "resourceId": row.resource_id,
        "result": row.result,
        "device": row.device,
        "summary": row.summary,
        "correctsEventId": row.corrects_event_id,
    }


@router.get("")
def list_audit(
    action: str | None = None,
    limit: int = Query(default=50, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    managed = managed_organization_ids(session, user)
    if not managed:
        raise HTTPException(status_code=404, detail="组织不存在")
    query = select(AuditEvent).where(AuditEvent.organization_id.in_(managed))
    if action:
        query = query.where(AuditEvent.action == action)
    rows = session.scalars(query.order_by(AuditEvent.timestamp.desc()).limit(limit)).all()
    return [audit_body(row) for row in rows]


@router.get("/export")
def export_audit(
    action: str | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    managed = managed_organization_ids(session, user)
    if not managed:
        raise HTTPException(status_code=404, detail="组织不存在")
    query = select(AuditEvent).where(AuditEvent.organization_id.in_(managed))
    if action:
        query = query.where(AuditEvent.action == action)
    rows = session.scalars(query.order_by(AuditEvent.timestamp.desc())).all()
    write_audit(session, user_id=user.id, organization_id=managed[0],
                action="audit.export", resource_type="audit",
                summary=f"导出审计 {len(rows)} 条")
    session.commit()
    return [audit_body(row) for row in rows]


@router.post("/corrections")
def create_correction(
    body: CorrectionRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    original = session.scalar(select(AuditEvent).where(AuditEvent.event_id == body.original_event_id))
    if original is None or original.organization_id not in managed_organization_ids(session, user):
        raise HTTPException(status_code=404, detail="原审计事件不存在")
    corrected = append_correction(session, original=original, user_id=user.id, summary=body.summary)
    session.commit()
    return audit_body(corrected)


@router.post("/purge")
def approve_purge(
    body: PurgeRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    managed = owner_organization_ids(session, user)
    if not managed:
        raise HTTPException(status_code=404, detail="组织不存在")
    cutoff = body.to or utcnow() + timedelta(days=36500)
    count = len(session.scalars(
        select(AuditEvent).where(
            AuditEvent.organization_id.in_(managed),
            AuditEvent.timestamp <= cutoff,
        )
    ).all())
    event = write_audit(session, user_id=user.id, organization_id=managed[0],
                        action="audit.purge_approved", resource_type="audit",
                        summary=f"批准清理范围至 {as_utc(cutoff).date()}，涉及 {count} 条；原因: {body.reason}")
    session.commit()
    return audit_body(event)


@router.post("/events")
def receive_audit_event(
    body: AuditEventRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    event = write_audit(session, user_id=body.userId, organization_id=body.organizationId,
                        space_id=body.spaceId, action=body.action, resource_type=body.resourceType,
                        resource_id=body.resourceId, result=body.result, device=body.device,
                        summary=body.summary)
    session.commit()
    return audit_body(event)
