"""T-091：后台任务创建、列表、取消、恢复与关闭。"""


def _space_with_member(owner_client, member_client, name: str = "后台任务组织"):
    org = owner_client.post("/api/v1/organizations", json={"name": name}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "研发部"}).json()
    space = owner_client.post(
        f"/api/v1/departments/{dept['id']}/project-spaces",
        json={"name": "自动化空间"},
    ).json()
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    member_id = member_client.get("/api/v1/auth/me").json()["userId"]
    owner_client.post(
        f"/api/v1/project-spaces/{space['id']}/members",
        json={"user_id": member_id, "role": "member"},
    )
    return org, dept, space


def test_background_job_can_be_listed_and_cancelled(owner_client):
    _, _, space = _space_with_member(owner_client, owner_client, "列表组织")
    job = owner_client.post("/api/v1/jobs", json={"spaceId": space["id"], "kind": "acp"}).json()
    assert owner_client.get("/api/v1/jobs").json()[0]["id"] == job["id"]
    cancelled = owner_client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_job_is_bound_to_user_space_and_plugin(owner_client):
    _, _, space = _space_with_member(owner_client, owner_client, "关联组织")
    job = owner_client.post(
        "/api/v1/jobs",
        json={"spaceId": space["id"], "kind": "acp", "inputSummary": "整理周报"},
    ).json()
    assert job["userId"]
    assert job["spaceId"] == space["id"]
    assert job["pluginId"] == "acp"
    assert job["inputSummary"] == "整理周报"
    assert job["createdAt"] and job["updatedAt"]


def test_resume_and_close_semantics(owner_client):
    _, _, space = _space_with_member(owner_client, owner_client, "恢复关闭组织")
    job = owner_client.post("/api/v1/jobs", json={"spaceId": space["id"], "kind": "acp"}).json()

    resumed = owner_client.post(f"/api/v1/jobs/{job['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["resumes"] == 1
    assert resumed.json()["status"] == "queued"

    closed = owner_client.post(f"/api/v1/jobs/{job['id']}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["alreadyClosed"] is False

    again = owner_client.post(f"/api/v1/jobs/{job['id']}/close")
    assert again.status_code == 200
    assert again.json()["alreadyClosed"] is True

    # closed 是终态：不可再恢复
    assert owner_client.post(f"/api/v1/jobs/{job['id']}/resume").status_code == 409

    actions = [row["action"] for row in owner_client.get("/api/v1/audit").json()]
    assert {"acp.job.start", "acp.job.resume", "acp.job.close"} <= set(actions)


def test_state_changes_are_audited_and_denied_access_is_recorded(owner_client, member_client):
    _, _, space = _space_with_member(owner_client, member_client, "审计组织")
    job = owner_client.post("/api/v1/jobs", json={"spaceId": space["id"], "kind": "acp"}).json()
    owner_client.post(f"/api/v1/jobs/{job['id']}/cancel")

    actions = [row["action"] for row in owner_client.get("/api/v1/audit").json()]
    assert {"acp.job.start", "acp.job.cancel"} <= set(actions)

    # 非成员：读写都是 404，并留下 denied 审计
    other_org = owner_client.post("/api/v1/organizations", json={"name": "隔离组织"}).json()
    other_dept = owner_client.post(
        f"/api/v1/organizations/{other_org['id']}/departments", json={"name": "D"}
    ).json()
    other_space = owner_client.post(
        f"/api/v1/departments/{other_dept['id']}/project-spaces", json={"name": "S"}
    ).json()
    assert member_client.post("/api/v1/jobs", json={"spaceId": other_space["id"], "kind": "acp"}).status_code == 404
    # 本空间任务：成员可读
    assert owner_client.get(f"/api/v1/jobs/{job['id']}").status_code == 200
    assert member_client.get(f"/api/v1/jobs/{job['id']}").status_code == 200
    # 隔离空间任务：非成员读不到（404）
    foreign_job = owner_client.post("/api/v1/jobs", json={"spaceId": other_space["id"], "kind": "acp"}).json()
    assert member_client.get(f"/api/v1/jobs/{foreign_job['id']}").status_code == 404
    denied = [row for row in owner_client.get("/api/v1/audit").json() if row["result"] == "denied"]
    assert denied


def test_unauthenticated_and_unknown_job(api, owner_client):
    assert api.post("/api/v1/jobs", json={"spaceId": "s", "kind": "acp"}).status_code == 401
    assert owner_client.get("/api/v1/jobs/does-not-exist").status_code == 404
