import uuid


def seed_usage(owner_client, space_id, model, cost, source, total):
    org = owner_client.post("/api/v1/organizations", json={"name": f"报表组织-{uuid.uuid4().hex[:8]}"}).json()
    user_id = owner_client.get("/api/v1/auth/me").json()["userId"]
    payload = {
        "usageId": str(uuid.uuid4()),
        "organizationId": org["id"],
        "spaceId": space_id,
        "userId": user_id,
        "provider": "deepseek",
        "model": model,
        "estimatedCost": cost,
        "source": source,
    }
    if total is not None:
        payload["totalTokens"] = total
    assert owner_client.post("/api/v1/usage", json=payload).status_code == 200
    return org


def test_usage_report_groups_by_user_space_and_model(owner_client):
    org = seed_usage(owner_client, None, "m1", 0.1, "dsh_event", 100)
    for group in ("user", "space", "model"):
        body = owner_client.get(f"/api/v1/reports/usage?organizationId={org['id']}&groupBy={group}").json()
        assert body["rows"] and "total" in body
    assert owner_client.get(
        f"/api/v1/reports/usage?organizationId={org['id']}&groupBy=user"
    ).json()["unknownCount"] >= 0


def test_estimated_and_precise_rows_are_separated(owner_client):
    org = seed_usage(owner_client, "s1", "m1", 0.1, "dsh_event", 100)
    seed_usage(owner_client, "s1", "m2", 0.2, "adapter_estimate", None)
    body = owner_client.get(
        f"/api/v1/reports/usage?organizationId={org['id']}&groupBy=model"
    ).json()
    assert {"estimated", "precise"} <= set(body["total"].keys())
    assert body["total"]["precise"]["totalTokens"] == 100
    assert body["total"]["estimated"]["totalTokens"] is None


def test_missing_dimension_is_not_zero(owner_client):
    org = seed_usage(owner_client, None, "m1", 0.1, "manual_import", 10)
    body = owner_client.get(
        f"/api/v1/reports/usage?organizationId={org['id']}&groupBy=space"
    ).json()
    assert body["rows"][0]["dimensionId"] == "unknown"
    assert body["rows"][0]["unknownCount"] == 1
