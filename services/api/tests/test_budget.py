import uuid


def setup_budget(owner_client):
    org = owner_client.post("/api/v1/organizations", json={"name": f"预算组织-{uuid.uuid4().hex[:8]}"}).json()
    response = owner_client.post(
        "/api/v1/budget/policies",
        json={"organizationId": org["id"], "scope": "organization", "monthlyLimit": 1, "softThresholdPercent": 80},
    )
    assert response.status_code == 200
    user_id = owner_client.get("/api/v1/auth/me").json()["userId"]
    return org, user_id


def spend(owner_client, org, user_id, amount, index):
    return owner_client.post(
        "/api/v1/budget/spend",
        json={
            "usageId": str(uuid.uuid4()),
            "organizationId": org["id"],
            "userId": user_id,
            "provider": "deepseek",
            "model": "m",
            "estimatedCost": amount,
            "source": "manual_import",
        },
    )


def test_soft_threshold_warns_and_hard_threshold_blocks(owner_client):
    org, user_id = setup_budget(owner_client)
    spend(owner_client, org, user_id, 0.10, 1)
    assert owner_client.get(f"/api/v1/budget/summary?organizationId={org['id']}").json()["state"] == "ok"
    spend(owner_client, org, user_id, 0.80, 2)
    assert owner_client.get(f"/api/v1/budget/summary?organizationId={org['id']}").json()["state"] == "soft"
    spend(owner_client, org, user_id, 0.20, 3)
    assert owner_client.get(f"/api/v1/budget/summary?organizationId={org['id']}").json()["state"] == "hard"


def test_hard_block_returns_explicit_reason_not_silent_failure(owner_client):
    org, user_id = setup_budget(owner_client)
    spend(owner_client, org, user_id, 1.10, 1)
    response = owner_client.post(
        "/api/v1/sessions",
        json={"organizationId": org["id"], "spaceId": None},
    )
    assert response.status_code == 402
    assert response.json()["detail"]["reason"] == "budget_exceeded"
    assert response.json()["detail"]["message"]


def test_budget_update_is_audited(owner_client):
    org, _ = setup_budget(owner_client)
    audits = owner_client.get("/api/v1/audit?action=budget.update").json()
    assert any(row["organizationId"] == org["id"] for row in audits)
