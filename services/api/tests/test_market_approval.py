"""T-102：插件白名单、安装审批与个人/企业模式差异。"""


def _org(owner_client, name: str = "市场治理组织"):
    org = owner_client.post("/api/v1/organizations", json={"name": name}).json()
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    return org


def test_unwhitelisted_plugin_cannot_be_installed(owner_client, member_client):
    org = _org(owner_client)
    response = member_client.post(
        "/api/v1/market/install",
        json={"pluginId": "unknown.plugin", "organizationId": org["id"]},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "not_whitelisted"

    audits = owner_client.get("/api/v1/audit").json()
    assert any(
        row["action"] == "plugin.install" and row["result"] == "denied" and row["resourceId"] == "unknown.plugin"
        for row in audits
    )


def test_approved_install_is_audited(owner_client):
    org = _org(owner_client, "白名单组织")
    whitelisted = owner_client.post(
        "/api/v1/market/whitelist",
        json={
            "organizationId": org["id"],
            "pluginId": "worknexus.knowledge",
            "version": "1.0.0",
            "dshCompatibility": ">=0.2.0-rc.1 <0.3.0",
            "hostCoreCompatibility": ">=1.0.0",
        },
    )
    assert whitelisted.status_code == 200, whitelisted.text

    installed = owner_client.post(
        "/api/v1/market/install",
        json={"pluginId": "worknexus.knowledge", "organizationId": org["id"]},
    )
    assert installed.status_code == 200
    body = installed.json()
    assert body["enforced"] is True
    assert body["delegatedTo"] == "@deepseek-ai/dsh-plugin-manager"

    actions = {row["action"] for row in owner_client.get("/api/v1/audit").json()}
    assert {"market.whitelist.update", "plugin.install"} <= actions


def test_approval_flow_is_traceable(owner_client):
    org = _org(owner_client, "审批组织")
    requested = owner_client.post(
        "/api/v1/market/approvals",
        json={"organizationId": org["id"], "pluginId": "worknexus.docgraph", "version": "1.0.0",
              "action": "install"},
    ).json()
    assert requested["status"] == "pending"
    assert requested["requestedByUserId"]

    decided = owner_client.post(
        f"/api/v1/market/approvals/{requested['id']}/decision",
        json={"decision": "approved", "reason": "已评估权限范围"},
    ).json()
    assert decided["status"] == "approved"
    assert decided["decidedByUserId"] == requested["requestedByUserId"]
    assert decided["decidedAt"] and decided["reason"] == "已评估权限范围"

    # 审批通过后自动进入白名单，可被安装
    listed = owner_client.get("/api/v1/market/whitelist", params={"organizationId": org["id"]}).json()
    assert any(row["pluginId"] == "worknexus.docgraph" for row in listed)
    assert owner_client.post(
        "/api/v1/market/install",
        json={"pluginId": "worknexus.docgraph", "organizationId": org["id"]},
    ).status_code == 200

    # 重复决策返回 409
    assert owner_client.post(
        f"/api/v1/market/approvals/{requested['id']}/decision", json={"decision": "rejected"}
    ).status_code == 409

    actions = {row["action"] for row in owner_client.get("/api/v1/audit").json()}
    assert {"market.approval.request", "market.approval.decide"} <= actions


def test_personal_mode_does_not_enforce_whitelist(owner_client, member_client):
    org = _org(owner_client, "个人模式组织")
    personal = member_client.post(
        "/api/v1/market/install",
        json={"pluginId": "third.party.plugin", "organizationId": org["id"], "mode": "personal"},
    )
    assert personal.status_code == 200
    body = personal.json()
    assert body["mode"] == "personal"
    assert body["enforced"] is False

    actions = [row["action"] for row in owner_client.get("/api/v1/audit").json()]
    assert "market.install_requested" in actions

    # 企业模式（默认）仍然强制白名单
    assert member_client.post(
        "/api/v1/market/install",
        json={"pluginId": "third.party.plugin", "organizationId": org["id"]},
    ).status_code == 403


def test_whitelist_requires_admin(owner_client, member_client):
    org = _org(owner_client, "越权白名单组织")
    assert member_client.post(
        "/api/v1/market/whitelist",
        json={"organizationId": org["id"], "pluginId": "x", "version": "1.0.0"},
    ).status_code == 404
    assert member_client.get(
        "/api/v1/market/whitelist", params={"organizationId": org["id"]}
    ).status_code == 200
