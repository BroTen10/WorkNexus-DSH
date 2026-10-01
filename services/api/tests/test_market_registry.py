"""T-101：私有插件源配置（控制面侧）。"""


def _org(owner_client, name: str = "私有源组织"):
    return owner_client.post("/api/v1/organizations", json={"name": name}).json()


def test_admin_configures_and_reads_private_registry(owner_client):
    org = _org(owner_client)
    created = owner_client.post(
        "/api/v1/market/registry",
        json={
            "organizationId": org["id"],
            "baseUrl": "https://registry.corp.local",
            "authRef": "official-credentials:registry-token",
            "timeoutMs": 2500,
            "fallbackRegistries": ["https://mirror.corp.local"],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["baseUrl"] == "https://registry.corp.local"
    assert body["timeoutMs"] == 2500
    assert body["fallbackRegistries"] == ["https://mirror.corp.local"]

    fetched = owner_client.get("/api/v1/market/registry", params={"organizationId": org["id"]}).json()
    assert fetched["baseUrl"] == "https://registry.corp.local"
    assert fetched["authRef"] == "official-credentials:registry-token"

    # 重复配置是更新而不是新增（复用 ExternalService 单条台账）
    updated = owner_client.post(
        "/api/v1/market/registry",
        json={"organizationId": org["id"], "baseUrl": "https://registry2.corp.local"},
    ).json()
    assert updated["id"] == body["id"]
    assert updated["baseUrl"] == "https://registry2.corp.local"
    assert updated["fallbackRegistries"] == []

    actions = [row["action"] for row in owner_client.get("/api/v1/audit").json()]
    assert "market.registry.update" in actions


def test_unconfigured_registry_reads_as_unconfigured(owner_client):
    org = _org(owner_client, "未配置组织")
    body = owner_client.get("/api/v1/market/registry", params={"organizationId": org["id"]}).json()
    assert body["status"] == "unconfigured"
    assert body["baseUrl"] is None


def test_registry_requires_admin_and_valid_url(owner_client, member_client):
    org = _org(owner_client, "越权私有源组织")
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    assert member_client.post(
        "/api/v1/market/registry",
        json={"organizationId": org["id"], "baseUrl": "https://registry.corp.local"},
    ).status_code == 404
    assert member_client.get(
        "/api/v1/market/registry", params={"organizationId": org["id"]}
    ).status_code == 200
    assert owner_client.post(
        "/api/v1/market/registry",
        json={"organizationId": org["id"], "baseUrl": "ftp://registry"},
    ).status_code == 400
