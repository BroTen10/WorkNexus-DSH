"""三层预算评估：组织 / 部门或项目空间 / 用户月度。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BudgetPolicy, UsageRecord
from app.models.identity import utcnow


@dataclass(frozen=True)
class BudgetState:
    state: str
    consumed: Decimal
    limit: Decimal | None
    soft_percent: int
    hard_percent: int


def month_start(now: datetime | None = None) -> datetime:
    current = as_utc_datetime(now or utcnow())
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def as_utc_datetime(value: datetime) -> datetime:
    from app.models.identity import as_utc

    return as_utc(value)


def consumed_amount(session: Session, organization_id: str, start: datetime) -> Decimal:
    total = session.scalar(
        select(func.coalesce(func.sum(UsageRecord.estimated_cost), 0)).where(
            UsageRecord.organization_id == organization_id,
            UsageRecord.timestamp >= start,
        )
    )
    return Decimal(str(total or 0))


def evaluate_budget(session: Session, organization_id: str, period: datetime | None = None) -> BudgetState:
    start = month_start(period)
    policy = session.scalar(
        select(BudgetPolicy).where(
            BudgetPolicy.organization_id == organization_id,
            BudgetPolicy.scope == "organization",
            BudgetPolicy.status == "active",
        )
    )
    if policy is None:
        return BudgetState("ok", consumed_amount(session, organization_id, start), None, 100, 100)
    limit = Decimal(policy.monthly_limit)
    soft_limit = limit * Decimal(policy.soft_threshold_percent) / Decimal(100)
    hard_limit = limit * Decimal(policy.hard_threshold_percent) / Decimal(100)
    consumed = consumed_amount(session, organization_id, start)
    if consumed >= hard_limit:
        state = "hard"
    elif consumed >= soft_limit:
        state = "soft"
    else:
        state = "ok"
    return BudgetState(state, consumed, limit, policy.soft_threshold_percent, policy.hard_threshold_percent)
