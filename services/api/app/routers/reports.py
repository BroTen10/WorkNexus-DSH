from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import UsageRecord
from app.models.identity import as_utc
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def bucket(rows: list[UsageRecord]) -> dict[str, Any]:
    precise = [row for row in rows if row.source == "dsh_event"]
    estimated = [row for row in rows if row.source != "dsh_event"]
    precise_tokens = [row.total_tokens for row in precise if row.total_tokens is not None]
    estimated_tokens = [row.total_tokens for row in estimated if row.total_tokens is not None]
    return {
        "recordCount": len(rows),
        "unknownCount": sum(1 for row in rows if row.total_tokens is None),
        "totalTokens": sum(precise_tokens + estimated_tokens) if precise_tokens or estimated_tokens else None,
        "estimatedCost": str(sum((row.estimated_cost or Decimal("0") for row in rows), Decimal("0"))),
        "precise": {
            "recordCount": len(precise),
            "totalTokens": sum(precise_tokens) if precise_tokens else None,
            "unknownTokenCount": sum(1 for row in precise if row.total_tokens is None),
        },
        "estimated": {
            "recordCount": len(estimated),
            "totalTokens": sum(estimated_tokens) if estimated_tokens else None,
            "unknownTokenCount": sum(1 for row in estimated if row.total_tokens is None),
        },
    }


@router.get("/usage")
def usage_report(
    organizationId: str,
    groupBy: Literal["user", "space", "model"] = Query(default="model"),
    user = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organizationId)
    rows = list(session.scalars(
        select(UsageRecord).where(UsageRecord.organization_id == organizationId)
    ).all())
    grouped: dict[str, list[UsageRecord]] = defaultdict(list)
    for row in rows:
        if groupBy == "user":
            dimension_id = row.user_id
        elif groupBy == "space":
            dimension_id = row.space_id or "unknown"
        elif groupBy == "model":
            dimension_id = row.model
        grouped[dimension_id].append(row)
    report_rows = []
    for dimension_id, values in grouped.items():
        body = bucket(values)
        report_rows.append({
            "dimensionId": dimension_id,
            "dimensionName": dimension_id,
            **body,
            "unknownCount": 1 if dimension_id == "unknown" else 0,
            "unknownTokenCount": body["unknownCount"],
        })
    return {
        "groupBy": groupBy,
        "total": bucket(rows),
        "rows": report_rows,
        "unknownCount": sum(1 for row in rows if row.total_tokens is None),
        "noData": not rows,
        "message": "无数据" if not rows else None,
    }
