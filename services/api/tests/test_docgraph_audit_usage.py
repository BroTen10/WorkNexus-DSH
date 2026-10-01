"""T-074：DocGraph 权限、审计与用量三件套。"""

import pytest


def _space_with_member(owner_client, member_client, name: str = "审计组织"):
    org = owner_client.post("/api/v1/organizations", json={"name": name}).json()
    dept = owner_client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "研发部"}).json()
    space = owner_client.post(
        f"/api/v1/departments/{dept['id']}/project-spaces",
        json={"name": "审查空间"},
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
def submitted_job(owner_client):
    _, _, space = _space_with_member(owner_client, owner_client, "提交夹具组织")
    response = owner_client.post(
        "/api/v1/docgraph/tasks",
        json={"spaceId": space["id"], "documentId": "d1", "contractId": "c1"},
    )
    assert response.status_code == 202, response.text
    return response.json()["jobId"], space


def test_submit_view_and_cancel_are_audited(owner_client, submitted_job):
    job_id, _ = submitted_job
    viewed = owner_client.get(f"/api/v1/docgraph/jobs/{job_id}")
    assert viewed.status_code == 200
    assert viewed.json()["jobId"] == job_id

    cancelled = owner_client.post(f"/api/v1/docgraph/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["remoteSupported"] is False
    assert "docgraph-unsupported" in body["detail"]

    actions = {row["action"] for row in owner_client.get("/api/v1/audit").json()}
    assert {"docgraph.submit", "docgraph.view", "docgraph.cancel"} <= actions


def test_token_usage_is_recorded_per_job(owner_client, submitted_job):
    job_id, _ = submitted_job
    payload = owner_client.get("/api/v1/usage").json()
    rows = [row for row in payload["rows"] if row["pluginId"] == "docgraph"]
    assert len(rows) == 1
    row = rows[0]
    assert row["usageId"] == f"docgraph:{job_id}"
    assert row["source"] == "adapter_estimate"
    assert row["provider"] == "docgraph" and row["model"] == "docgraph-review"
    assert row["promptTokens"] is None
    assert row["completionTokens"] is None
    assert row["totalTokens"] is None
    assert payload["estimatedCount"] >= 1


def test_non_member_cannot_view_or_cancel_and_is_audited(owner_client, member_client, submitted_job):
    job_id, _ = submitted_job
    assert member_client.get(f"/api/v1/docgraph/jobs/{job_id}").status_code == 404
    assert member_client.post(f"/api/v1/docgraph/jobs/{job_id}/cancel").status_code == 404
    audits = owner_client.get("/api/v1/audit").json()
    denied = [row for row in audits
              if row["action"] in {"docgraph.submit", "docgraph.view"} and row["result"] == "denied"]
    assert denied


def test_unknown_job_is_404(owner_client):
    assert owner_client.get("/api/v1/docgraph/jobs/not-a-job").status_code == 404
    assert owner_client.post("/api/v1/docgraph/jobs/not-a-job/cancel").status_code == 404
