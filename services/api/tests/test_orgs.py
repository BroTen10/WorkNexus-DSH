def test_owner_can_create_org_department_and_space(owner_client):
    org = owner_client.post("/api/v1/organizations", json={"name": "示例组织"}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "研发部"}).json()
    space = owner_client.post(
        f"/api/v1/departments/{dept['id']}/project-spaces",
        json={"name": "DocGraph 接入"},
    ).json()
    assert space["departmentId"] == dept["id"]
    members = owner_client.get(f"/api/v1/organizations/{org['id']}/members").json()
    assert members[0]["role"] == "owner"


def test_unauthenticated_create_is_rejected(api):
    response = api.post("/api/v1/organizations", json={"name": "未登录组织"})
    assert response.status_code == 401


def test_non_owner_cannot_create_department(owner_client, member_client):
    org = owner_client.post("/api/v1/organizations", json={"name": "权限组织"}).json()
    response = member_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "越权部门"})
    assert response.status_code == 404


def test_duplicate_organization_name_is_rejected(owner_client):
    owner_client.post("/api/v1/organizations", json={"name": "唯一组织"})
    assert owner_client.post("/api/v1/organizations", json={"name": "唯一组织"}).status_code == 409


def test_update_writes_audit_and_owner_transfer_requires_owner(owner_client, member_client):
    org = owner_client.post("/api/v1/organizations", json={"name": "变更组织"}).json()
    updated = owner_client.patch(f"/api/v1/organizations/{org['id']}", json={"name": "变更组织-2"})
    assert updated.status_code == 200
    audits = owner_client.get("/api/v1/audit").json()
    assert any(row["action"] == "organization.update" for row in audits)

    transfer = owner_client.post(
        f"/api/v1/organizations/{org['id']}/transfer-owner",
        json={"user_id": member_client.get("/api/v1/auth/me").json()["userId"]},
    )
    assert transfer.status_code == 200
    members = owner_client.get(f"/api/v1/organizations/{org['id']}/members").json()
    assert any(row["userId"] == member_client.get("/api/v1/auth/me").json()["userId"] and row["role"] == "owner" for row in members)


def test_archive_space_is_visible_in_status(owner_client):
    org = owner_client.post("/api/v1/organizations", json={"name": "归档组织"}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "D"}).json()
    space = owner_client.post(f"/api/v1/departments/{dept['id']}/project-spaces", json={"name": "S"}).json()
    archived = owner_client.delete(f"/api/v1/project-spaces/{space['id']}")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
