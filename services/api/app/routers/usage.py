from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import UsageRecord
from app.models.identity import as_utc, utcnow
from app.security.dependencies import get_current_user
from app.services.audit import write_audit

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


class UsageRequest(BaseModel):
    usageId: str
    organizationId: str
    spaceId: str | None = None
    userId: str
    sessionId: str | None = None
    pluginId: str | None = None
    provider: str
    model: str
    promptTokens: int | None = None
    completionTokens: int | None = None
    totalTokens: int | None = None
    estimatedCost: float | None = None
    source: Literal["dsh_event", "adapter_estimate", "manual_import"]


def usage_body(row: UsageRecord) -> dict[str, Any]:
    return {
        "usageId": row.usage_id,
        "timestamp": as_utc(row.timestamp).isoformat(),
        "organizationId": row.organization_id,
        "spaceId": row.space_id,
        "userId": row.user_id,
        "sessionId": row.session_id,
        "pluginId": row.plugin_id,
        "provider": row.provider,
        "model": row.model,
        "promptTokens": row.prompt_tokens,
        "completionTokens": row.completion_tokens,
        "totalTokens": row.total_tokens,
        "estimatedCost": row.estimated_cost,
        "source": row.source,
    }


@router.post("")
def record_usage(
    body: UsageRequest,
    user = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    existing = session.scalar(select(UsageRecord).where(UsageRecord.usage_id == body.usageId))
    if existing is not None:
        return usage_body(existing)
    row = UsageRecord(
        usage_id=body.usageId,
        organization_id=body.organizationId,
        space_id=body.spaceId,
        user_id=body.userId,
        session_id=body.sessionId,
        plugin_id=body.pluginId,
        provider=body.provider,
        model=body.model,
        prompt_tokens=body.promptTokens,
        completion_tokens=body.completionTokens,
        total_tokens=body.totalTokens,
        estimated_cost=Decimal(str(body.estimatedCost)) if body.estimatedCost is not None else None,
        source=body.source,
        retain_until=utcnow(),
    )
    session.add(row)
    session.flush()
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                space_id=body.spaceId, action="usage.record", resource_type="usage",
                resource_id=row.usage_id, summary="写入用量记录")
    session.commit()
    return usage_body(row)


@router.get("")
def query_usage(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(default=100, le=500),
    user = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(UsageRecord).order_by(UsageRecord.timestamp.desc()).limit(limit)
    rows = session.scalars(query).all()
    return {
        "rows": [usage_body(row) for row in rows],
        "estimatedCount": sum(1 for row in rows if row.source != "dsh_event"),
    }
