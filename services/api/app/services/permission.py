"""服务端权威权限矩阵。

客户端只能用同形矩阵做 UI 预判；最终必须由本模块/控制面裁决。
"""

from typing import Any, Mapping

from fastapi import HTTPException

ACTIONS = frozenset({
    # T-030 契约 Action
    "space.read", "space.write", "member.invite", "member.remove", "role.assign",
    "plugin.enable", "plugin.disable", "audit.read", "usage.read", "budget.write",
    "kb.retrieve", "kb.bind", "docgraph.submit", "docgraph.read", "session.create",
    # 组织治理动作：服务端扩展，不开放给企业插件声明
    "organization.delete", "ownership.transfer",
})

PERMISSION_MATRIX: dict[str, set[str]] = {
    "owner": ACTIONS,
    "admin": ACTIONS - {"organization.delete", "ownership.transfer"},
    "member": {
        "space.read", "space.write", "kb.retrieve", "kb.bind",
        "docgraph.submit", "docgraph.read", "session.create",
    },
    "viewer": {
        "space.read", "kb.retrieve", "docgraph.read", "usage.read",
    },
}


def can(actor: Mapping[str, Any], action: str, resource: Mapping[str, Any] | None = None) -> bool:
    role = actor.get("role") if isinstance(actor, Mapping) else getattr(actor, "role", None)
    if not isinstance(role, str):
        return False
    return action in PERMISSION_MATRIX.get(role, set())


def require_permission(
    actor: Mapping[str, Any],
    action: str,
    resource: Mapping[str, Any] | None = None,
) -> None:
    if not can(actor, action, resource):
        raise HTTPException(status_code=404, detail="资源不存在")


def matrix_is_complete() -> bool:
    roles = {"owner", "admin", "member", "viewer"}
    return all(role in PERMISSION_MATRIX and PERMISSION_MATRIX[role] <= ACTIONS for role in roles)
