"""插件市场控制面：企业私有源配置（T-101，需求书 P6B-F01）。

落地方式：复用 T-041 的 `ExternalService`（`service_type='plugin-registry'`），不新增第二套
外部服务台账；地址、凭据引用、超时与回退源写在 `configJson` 里。

边界（§5.4 第 3 条、P6B 验收 4）：私有源不可用**不影响客户端启动**——控制面只提供配置，
真正的可用性判断在客户端（`createPrivateSource().list()` 降级为 `installed-only`）。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import ExternalService, User
from app.routers.orgs import require_org_role
from app.security.dependencies import get_current_user
from app.services.audit import write_audit

router = APIRouter(prefix="/api/v1/market", tags=["market"])

SERVICE_TYPE = "plugin-registry"


class RegistryRequest(BaseModel):
    organizationId: str
    baseUrl: str = Field(min_length=1, max_length=2000)
    authRef: str | None = Field(default=None, max_length=200)
    timeoutMs: int = Field(default=4000, ge=500, le=60000)
    fallbackRegistries: list[str] = Field(default_factory=list, max_length=10)


def registry_body(row: ExternalService) -> dict[str, Any]:
    config = json.loads(row.config_json) if row.config_json else {}
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "baseUrl": row.endpoint_url,
        "authRef": row.auth_ref,
        "timeoutMs": config.get("timeoutMs", 4000),
        "fallbackRegistries": config.get("fallbackRegistries", []),
        "status": row.status,
    }


def _require_http_url(url: str) -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="baseUrl 必须是 http/https 绝对地址")
    return url


@router.post("/registry")
def configure_registry(
    body: RegistryRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, body.organizationId, "admin")
    _require_http_url(body.baseUrl)
    for fallback in body.fallbackRegistries:
        _require_http_url(fallback)

    row = session.scalar(
        select(ExternalService).where(
            ExternalService.organization_id == body.organizationId,
            ExternalService.service_type == SERVICE_TYPE,
        )
    )
    config_json = json.dumps(
        {"timeoutMs": body.timeoutMs, "fallbackRegistries": body.fallbackRegistries},
        ensure_ascii=False,
    )
    if row is None:
        row = ExternalService(
            organization_id=body.organizationId,
            service_type=SERVICE_TYPE,
            endpoint_url=body.baseUrl,
            auth_ref=body.authRef,
            config_json=config_json,
        )
        session.add(row)
    else:
        row.endpoint_url = body.baseUrl
        row.auth_ref = body.authRef
        row.config_json = config_json
    session.flush()
    write_audit(session, user_id=user.id, organization_id=body.organizationId,
                action="market.registry.update", resource_type="external_service", resource_id=row.id,
                summary=f"配置私有插件源 {body.baseUrl}")
    session.commit()
    return registry_body(row)


@router.get("/registry")
def get_registry(
    organization_id: str = Query(alias="organizationId"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    require_org_role(session, user, organization_id)
    row = session.scalar(
        select(ExternalService).where(
            ExternalService.organization_id == organization_id,
            ExternalService.service_type == SERVICE_TYPE,
        )
    )
    if row is None:
        return {
            "organizationId": organization_id,
            "baseUrl": None,
            "authRef": None,
            "timeoutMs": 4000,
            "fallbackRegistries": [],
            "status": "unconfigured",
        }
    return registry_body(row)
