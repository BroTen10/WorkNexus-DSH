"""知识库检索日志（T-064，需求书 P3-F08）。

只追加：
  - 写入接口记录请求、命中数量、知识库 ID、用户、空间与耗时；
  - **不保存查询正文与文档正文**——只保存 `sha256(query)` 的前 64 位十六进制与查询长度；
  - 不提供更新/删除接口（留存与清理走 §4.2.4 的治理路径）。

权限：写入需要组织成员（执行检索的人自己上报）；读取收敛到**至少 admin**（管理视图）。
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import KnowledgeBase, KnowledgeRetrievalLog, User
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/api/v1", tags=["knowledge"])

MAX_QUERY_LENGTH = 4000


class RetrievalLogRequest(BaseModel):
    knowledgeBaseId: str
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    hitCount: int = Field(ge=0, le=1000)
    durationMs: int = Field(ge=0, le=600_000)
    spaceId: str | None = Field(default=None, max_length=36)


def retrieval_log_body(row: KnowledgeRetrievalLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "knowledgeBaseId": row.knowledge_base_id,
        "organizationId": row.organization_id,
        "spaceId": row.space_id,
        "userId": row.user_id,
        "queryHash": row.query_hash,
        "queryLength": row.query_length,
        "hitCount": row.hit_count,
        "durationMs": row.duration_ms,
        "retentionDays": row.retention_days,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def query_digest(query: str) -> tuple[str, int]:
    """返回（查询摘要哈希，查询长度）；调用方不得保存正文。"""
    return hashlib.sha256(query.encode("utf-8")).hexdigest(), len(query)


@router.post("/knowledge-retrieval-logs")
def record_retrieval_log(
    body: RetrievalLogRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    knowledge_base = session.get(KnowledgeBase, body.knowledgeBaseId)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    require_org_role(session, user, knowledge_base.organization_id)
    digest, length = query_digest(body.query)
    row = KnowledgeRetrievalLog(
        knowledge_base_id=knowledge_base.id,
        organization_id=knowledge_base.organization_id,
        space_id=body.spaceId,
        user_id=user.id,
        query_hash=digest,
        query_length=length,
        hit_count=body.hitCount,
        duration_ms=body.durationMs,
    )
    session.add(row)
    session.commit()
    return retrieval_log_body(row)


@router.get("/knowledge-retrieval-logs")
def list_retrieval_logs(
    organization_id: str = Query(alias="organizationId"),
    knowledge_base_id: str | None = Query(default=None, alias="knowledgeBaseId"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    require_org_role(session, user, organization_id, "admin")
    statement = (
        select(KnowledgeRetrievalLog)
        .where(KnowledgeRetrievalLog.organization_id == organization_id)
        .order_by(KnowledgeRetrievalLog.created_at.desc())
        .limit(limit)
    )
    if knowledge_base_id is not None:
        statement = statement.where(KnowledgeRetrievalLog.knowledge_base_id == knowledge_base_id)
    return [retrieval_log_body(row) for row in session.scalars(statement).all()]
