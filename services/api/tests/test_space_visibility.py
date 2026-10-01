def create_org_department_space(client):
    org = client.post("/api/v1/organizations", json={"name": "可见组织"}).json()
    dept = client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "可见部门"}).json()
    space = client.post(f"/api/v1/departments/{dept['id']}/project-spaces", json={"name": "私有空间"}).json()
    return org, dept, space


def test_unauthorized_member_cannot_see_or_enter_space(owner_client, member_client):
    org, dept, space = create_org_department_space(owner_client)
    assert member_client.get(f"/api/v1/organizations/{org['id']}/project-spaces").json() == []
    assert member_client.get(f"/api/v1/project-spaces/{space['id']}").status_code == 404


def test_explicitly_authorized_member_can_see_space(owner_client, member_client):
    org, dept, space = create_org_department_space(owner_client)
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    member_id = member_client.get("/api/v1/auth/me").json()["userId"]
    owner_client.post(
        f"/api/v1/project-spaces/{space['id']}/members",
        json={"user_id": member_id, "role": "member"},
    )
    rows = member_client.get(f"/api/v1/organizations/{org['id']}/project-spaces").json()
    assert [row["id"] for row in rows] == [space["id"]]
    assert member_client.get(f"/api/v1/project-spaces/{space['id']}").status_code == 200


def test_personal_mode_returns_no_enterprise_spaces(owner_client, member_client):
    org, dept, space = create_org_department_space(owner_client)
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    member_id = member_client.get("/api/v1/auth/me").json()["userId"]
    owner_client.post(
        f"/api/v1/project-spaces/{space['id']}/members",
        json={"user_id": member_id, "role": "member"},
    )
    assert member_client.get(
        f"/api/v1/organizations/{org['id']}/project-spaces",
        headers={"X-WorkNexus-Mode": "personal"},
    ).json() == []
    assert member_client.get(
        f"/api/v1/project-spaces/{space['id']}",
        headers={"X-WorkNexus-Mode": "personal"},
    ).status_code == 404


def test_denied_access_is_audited(owner_client, member_client):
    org, dept, space = create_org_department_space(owner_client)
    member_client.get(f"/api/v1/project-spaces/{space['id']}")
    audits = owner_client.get("/api/v1/audit").json()
    assert any(
        row["action"] == "space.read" and row["result"] == "denied" and row["resourceId"] == space["id"]
        for row in audits
    )
