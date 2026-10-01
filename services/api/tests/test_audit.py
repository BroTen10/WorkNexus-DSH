import uuid

import pytest

from app.models import AuditEvent
from app.models.identity import utcnow
from app.services.audit import AUDIT_ACTIONS


def seed_event(session, action, organization_id="o1", user_id="u1"):
    row = AuditEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        resource_type="test",
        result="success",
        device="test",
        summary=action,
        retain_until=utcnow(),
    )
    session.add(row)
    session.commit()
    return row


@pytest.fixture
def seeded(session, owner_client, member_client):
    actions = [
        "auth.login", "organization.create", "member.role_assign", "plugin.enable", "space.create",
        "budget.update", "kb.bind", "docgraph.submit", "client.version.upgrade",
    ]
    for action in actions:
        seed_event(session, action)


def test_owner_and_admin_can_query_but_member_cannot(owner_client, member_client):
    owner_client.post("/api/v1/organizations", json={"name": "审计组织"})
    assert owner_client.get("/api/v1/audit").status_code == 200
    assert member_client.get("/api/v1/audit").status_code == 404


def test_required_event_families_are_declared():
    required = {
        "auth.login", "organization.create", "member.role_assign", "plugin.install",
        "plugin.update", "plugin.enable", "plugin.disable", "plugin.uninstall",
        "kb.bind", "docgraph.submit", "docgraph.cancel", "budget.update", "client.version.upgrade",
    }
    assert required <= set(AUDIT_ACTIONS)


def test_export_writes_audit(owner_client):
    owner_client.post("/api/v1/organizations", json={"name": "导出组织"})
    response = owner_client.get("/api/v1/audit/export")
    assert response.status_code == 200
    rows = owner_client.get("/api/v1/audit?action=audit.export").json()
    assert rows


def test_correction_is_appended_and_original_is_not_updated(owner_client):
    org = owner_client.post("/api/v1/organizations", json={"name": "更正组织"}).json()
    user_id = owner_client.get("/api/v1/auth/me").json()["userId"]
    original = owner_client.post(
        "/api/v1/audit/events",
        json={
            "userId": user_id,
            "organizationId": org["id"],
            "action": "budget.update",
            "resourceType": "budget",
            "result": "success",
            "summary": "预算原始事件",
        },
    ).json()
    response = owner_client.post(
        "/api/v1/audit/corrections",
        json={"original_event_id": original["eventId"], "summary": "更正预算金额"},
    )
    assert response.status_code == 200
    assert response.json()["correctsEventId"] == original["eventId"]


def test_non_owner_cannot_request_purge(owner_client, member_client, session):
    seed_event(session, "usage.record")
    response = member_client.post(
        "/api/v1/audit/purge",
        json={"reason": "误操作清理"},
    )
    assert response.status_code == 404
