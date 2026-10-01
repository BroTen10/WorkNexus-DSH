"""T-071：项目空间内的 DocGraph 任务提交与拒绝审计。"""


def _space_with_member(owner_client, member_client, name: str = "DocGraph 组织"):
    org = owner_client.post("/api/v1/organizations", json={"name": name}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "研发部"}).json()
    space = owner_client.post(
        f"/api/v1/departments/{dept['id']}/project-spaces",
        json={"name": "合同审查"},
    ).json()
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    member_id = member_client.get("/api/v1/auth/me").json()["userId"]
    granted = owner_client.post(
        f"/api/v1/project-spaces/{space['id']}/members",
        json={"user_id": member_id, "role": "member"},
    )
    assert granted.status_code == 200, granted.text
    return org, dept, space


def _other_space(owner_client, name: str = "隔离组织"):
    org = owner_client.post("/api/v1/organizations", json={"name": name}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "另一部门"}).json()
    space = owner_client.post(
        f"/api/v1/departments/{dept['id']}/project-spaces",
        json={"name": "另一空间"},
    ).json()
    return org, dept, space


def test_authorized_space_member_can_submit(owner_client, member_client):
    _, _, space = _space_with_member(owner_client, member_client)
    response = member_client.post(
        "/api/v1/docgraph/tasks",
        json={"spaceId": space["id"], "documentId": "d1", "contractId": "c1"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["jobId"]
    assert body["status"] == "queued"
    assert body["spaceId"] == space["id"] and body["mode"] == "review"
    assert body["remoteTaskId"] is None

    # 审计读取收敛到 owner/admin（普通成员无 audit.read），故由组织所有者读取
    actions = [row["action"] for row in owner_client.get("/api/v1/audit").json()]
    assert "docgraph.submit" in actions


def test_non_member_is_denied_and_audited(owner_client, member_client):
    _, _, other = _other_space(owner_client)
    response = member_client.post(
        "/api/v1/docgraph/tasks",
        json={"spaceId": other["id"], "documentId": "d1"},
    )
    assert response.status_code == 404
    audits = owner_client.get("/api/v1/audit").json()
    assert any(row["action"] == "docgraph.submit" and row["result"] == "denied" for row in audits)


def test_viewer_cannot_submit_but_can_read(owner_client, client_factory, mailer):
    """viewer 在矩阵里只有 `docgraph.read`，因此不能提交。"""
    org = owner_client.post("/api/v1/organizations", json={"name": "只读组织"}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "D"}).json()
    space = owner_client.post(f"/api/v1/departments/{dept['id']}/project-spaces", json={"name": "S"}).json()
    viewer = client_factory("viewer@example.com")
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "viewer@example.com", "role": "viewer"},
    )
    viewer_id = viewer.get("/api/v1/auth/me").json()["userId"]
    owner_client.post(
        f"/api/v1/project-spaces/{space['id']}/members",
        json={"user_id": viewer_id, "role": "viewer"},
    )
    denied = viewer.post("/api/v1/docgraph/tasks", json={"spaceId": space["id"], "documentId": "d1"})
    assert denied.status_code == 404
    assert viewer.get("/api/v1/docgraph/tasks", params={"spaceId": space["id"]}).status_code == 200


def test_unauthenticated_submit_is_rejected(api):
    response = api.post("/api/v1/docgraph/tasks", json={"spaceId": "s", "documentId": "d1"})
    assert response.status_code == 401


def test_unreachable_docgraph_does_not_block_submission(owner_client):
    """控制面只登记任务；DocGraph 不可达由插件侧健康检查暴露，不影响提交与本地状态。"""
    _, _, space = _other_space(owner_client, "不可达组织")
    response = owner_client.post(
        "/api/v1/docgraph/tasks",
        json={"spaceId": space["id"], "documentId": "d9", "mode": "analysis"},
    )
    assert response.status_code == 202
    assert response.json()["mode"] == "analysis"
