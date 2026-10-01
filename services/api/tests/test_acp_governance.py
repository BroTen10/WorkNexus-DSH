"""T-092：ACP 权限请求策略、审计与用量。"""

import pytest


def _space_with_member(owner_client, member_client, name: str = "ACP 治理组织"):
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


@pytest.fixture
def acp_job(owner_client, member_client):
    _, _, space = _space_with_member(owner_client, member_client, "ACP 任务夹具")
    job = owner_client.post(
        "/api/v1/jobs",
        json={"spaceId": space["id"], "kind": "acp", "inputSummary": "整理会议纪要"},
    ).json()
    return job, space


def test_permission_request_requires_policy_or_admin(owner_client, member_client, acp_job):
    job, _ = acp_job
    url = f"/api/v1/jobs/{job['id']}/permission-request"

    # 写类工具：普通成员被拒（需管理员确认），owner 视为管理员确认通过
    denied = member_client.post(url, json={"tool": "fs.write"})
    assert denied.status_code == 403
    assert denied.json()["detail"]["reason"] == "requires_admin_approval"

    allowed = owner_client.post(url, json={"tool": "fs.write"})
    assert allowed.status_code == 200
    assert allowed.json()["decidedBy"] == "admin"

    # 只读工具：策略自动放行
    auto = member_client.post(url, json={"tool": "fs.read"})
    assert auto.status_code == 200
    assert auto.json()["decidedBy"] == "policy"
    assert auto.json()["reason"] == "policy.auto_allowed"

    # 未知工具：默认拒绝（fail closed）
    unknown = member_client.post(url, json={"tool": "unknown.tool"})
    assert unknown.status_code == 403
    assert unknown.json()["detail"]["reason"] == "policy.default_deny"


def test_acp_sessions_enter_audit_and_usage(owner_client, acp_job):
    job, _ = acp_job
    owner_client.post(f"/api/v1/jobs/{job['id']}/permission-request", json={"tool": "fs.write"})

    actions = {row["action"] for row in owner_client.get("/api/v1/audit").json()}
    assert {"acp.job.start", "acp.permission.request"} <= actions

    payload = owner_client.get("/api/v1/usage").json()
    rows = [row for row in payload["rows"] if row["pluginId"] == "acp"]
    assert rows
    row = rows[0]
    assert row["usageId"] == f"acp:{job['id']}"
    assert row["source"] == "adapter_estimate"
    assert row["promptTokens"] is None and row["completionTokens"] is None and row["totalTokens"] is None


def test_permission_request_is_denied_and_audited_for_non_members(owner_client, member_client):
    org = owner_client.post("/api/v1/organizations", json={"name": "隔离治理组织"}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "D"}).json()
    space = owner_client.post(f"/api/v1/departments/{dept['id']}/project-spaces", json={"name": "S"}).json()
    job = owner_client.post("/api/v1/jobs", json={"spaceId": space["id"], "kind": "acp"}).json()

    assert member_client.post(
        f"/api/v1/jobs/{job['id']}/permission-request", json={"tool": "fs.read"}
    ).status_code == 404
    audits = owner_client.get("/api/v1/audit").json()
    assert any(row["action"] == "acp.job.start" and row["result"] == "denied" for row in audits)


def test_unknown_job_permission_request_is_404(owner_client):
    assert owner_client.post(
        "/api/v1/jobs/does-not-exist/permission-request", json={"tool": "fs.read"}
    ).status_code == 404
