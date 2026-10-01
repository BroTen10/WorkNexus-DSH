from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import BudgetPolicy, UsageRecord
from app.models.identity import utcnow
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user
from app.services.audit import write_audit
from app.services.budget import evaluate_budget

router = APIRouter(prefix="/api/v1", tags=["budget"])


class BudgetPolicyRequest(BaseModel):
    organizationId: str
    departmentId: str | None = None
    projectSpaceId: str | None = None
    userId: str | None = None
    scope: Literal["organization", "department", "project", "user"]
    monthlyLimit: int = Field(ge=0)
    softThresholdPercent: int = Field(default=80, ge=0, le=100)
    hardThresholdPercent: int = Field(default=100, ge=0, le=100)


class BudgetSpendRequest(BaseModel):
    usageId: str
    organizationId: str
    spaceId: str | None = None
    userId: str
    provider: str
    model: str
    estimatedCost: float
    source: Literal["dsh_event", "adapter_estimate", "manual_import"]


class BudgetSessionRequest(BaseModel):
    organizationId: str
    spaceId: str | None = None


def policy_body(row: BudgetPolicy) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "departmentId": row.department_id,
        "projectSpaceId": row.project_space_id,
        "userId": row.user_id,
        "scope": row.scope,
        "monthlyLimit": row.monthly_limit,
        "softThresholdPercent": row.soft_threshold_percent,
        "hardThresholdPercent": row.hard_threshold_percent,
        "status": row.status,
    }


def state_body(state) -> dict[str, Any]:
    return {
        "state": state.state,
        "consumed": str(state.consumed),
        "limit": str(state.limit) if state.limit is not None else None,
        "softThresholdPercent": state.soft_percent,
        "hardThresholdPercent": state.hard_percent,
    }


@router.post("/budget/policies")
def create_budget_policy(
    body: BudgetPolicyRequest,
    user = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "admin")
    row = BudgetPolicy(
        organization_id=body.organizationId,
        department_id=body.departmentId,
        project_space_id=body.projectSpaceId,
        user_id=body.userId,
        scope=body.scope,
        monthly_limit=body.monthlyLimit,
        soft_threshold_percent=body.softThresholdPercent,
        hard_threshold_percent=body.hardThresholdPercent,
    )
    session.add(row)
    session.flush()
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                action="budget.update", resource_type="budget", resource_id=row.id,
                summary=f"设置预算 {body.monthlyLimit}")
    session.commit()
    return policy_body(row)


@router.post("/budget/spend")
def record_spend(
    body: BudgetSpendRequest,
    user = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "member")
    existing = session.scalar(select(UsageRecord).where(UsageRecord.usage_id == body.usageId))
    if existing is None:
        row = UsageRecord(
            usage_id=body.usageId,
            organization_id=body.organizationId,
            space_id=body.spaceId,
            user_id=body.userId,
            provider=body.provider,
            model=body.model,
            estimated_cost=Decimal(str(body.estimatedCost)),
            source=body.source,
            retain_until=utcnow(),
        )
        session.add(row)
        session.flush()
    state = evaluate_budget(session, body.organizationId)
    session.commit()
    return state_body(state)


@router.get("/budget/summary")
def budget_summary(
    organizationId: str,
    user = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organizationId)
    return state_body(evaluate_budget(session, organizationId))


@router.post("/sessions")
def create_session_budget_gate(
    body: BudgetSessionRequest,
    user = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId)
    state = evaluate_budget(session, body.organizationId)
    if state.state == "hard":
        raise HTTPException(
            status_code=402,
            detail={
                "reason": "budget_exceeded",
                "message": "本月预算已达硬阈值，不能创建新会话或提交新请求",
            },
        )
    return {
        "accepted": True,
        "budgetState": state.state,
        "notice": "预算已进入软阈值提醒区间" if state.state == "soft" else None,
    }
