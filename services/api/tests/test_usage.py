import uuid

import pytest

from app.models import UsageRecord


def usage_payload(**overrides):
    payload = {
        "usageId": str(uuid.uuid4()),
        "organizationId": "org",
        "userId": "user",
        "provider": "deepseek",
        "model": "m",
        "source": "dsh_event",
    }
    payload.update(overrides)
    return payload


def test_usage_write_is_idempotent(owner_client):
    user_id = owner_client.get("/api/v1/auth/me").json()["userId"]
    payload = usage_prompt(owner_client, user_id, promptTokens=10, completionTokens=5)
    assert owner_client.post("/api/v1/usage", json=payload).status_code == 200
    assert owner_client.post("/api/v1/usage", json=payload).status_code == 200
    assert len(owner_client.get("/api/v1/usage").json()["rows"]) == 1


def test_usage_fields_may_be_null(owner_client):
    payload = usage_payload(
        organizationId=owner_client.post("/api/v1/organizations", json={"name": "空字段用量组织"}).json()["id"],
        userId=owner_client.get("/api/v1/auth/me").json()["userId"],
        source="manual_import",
    )
    assert owner_client.post("/api/v1/usage", json=payload).status_code == 200
    row = owner_client.get("/api/v1/usage").json()["rows"][0]
    assert row["totalTokens"] is None
    assert row["estimatedCost"] is None


def test_unknown_source_is_rejected(owner_client):
    payload = usage_prompt(owner_client, owner_client.get("/api/v1/auth/me").json()["userId"], source="guess")
    response = owner_client.post("/api/v1/usage", json=payload)
    assert response.status_code == 422


def test_usage_query_separates_null_and_zero(owner_client):
    payload = usage_prompt(owner_client, owner_client.get("/api/v1/auth/me").json()["userId"], source="manual_import")
    owner_client.post("/api/v1/usage", json=payload)
    body = owner_client.get("/api/v1/usage").json()
    assert body["rows"][0]["totalTokens"] is None
    assert "estimatedCount" in body


def usage_prompt(client, user_id, **overrides):
    org = client.post("/api/v1/organizations", json={"name": f"用量组织-{overrides.get('source', 'dsh_event')}-{user_id[:8]}"}).json()
    payload = usage_payload(organizationId=org["id"], userId=user_id, **overrides)
    if overrides.get("source") == "manual_import":
        payload["source"] = "manual_import"
    return payload
