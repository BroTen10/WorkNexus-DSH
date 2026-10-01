import time


def valid_report():
    return {
        "runtimeVersion": "0.2.0-rc.1",
        "platform": "win32",
        "architecture": "x64",
        "profileValidation": "ok",
        "pluginStates": [{"pluginId": "p", "state": "enabled"}],
        "errorType": "startup",
        "errorCode": "E_TEST",
        "errorSummary": "redacted",
        "timestamp": "2026-09-29T00:00:00Z",
        "anonymousInstallId": "install-1",
    }


def setup_owner(owner_client):
    org = owner_client.post("/api/v1/organizations", json={"name": "诊断组织"}).json()
    return org, owner_client


def test_accepts_whitelisted_fields(owner_client):
    response = owner_client.post(
        "/api/v1/diagnostics/reports",
        json=valid_report(),
        headers={"X-Organization-Id": "org"},
    )
    assert response.status_code == 202


def test_rejects_fields_outside_whitelist(owner_client):
    payload = valid_report()
    payload["prompt"] = "must not be accepted"
    response = owner_client.post("/api/v1/diagnostics/reports", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["rejectedFields"] == ["prompt"]


def test_personal_mode_rejects_all_reports(owner_client):
    response = owner_client.post(
        "/api/v1/diagnostics/reports",
        json=valid_report(),
        headers={"X-WorkNexus-Mode": "personal"},
    )
    assert response.status_code == 404


def test_only_owner_or_admin_can_view_and_viewing_is_audited(owner_client, member_client):
    owner_client.post("/api/v1/organizations", json={"name": "诊断查看组织"})
    owner_client.post("/api/v1/diagnostics/reports", json=valid_report())
    assert member_client.get("/api/v1/diagnostics/reports").status_code == 404
    assert owner_client.get("/api/v1/diagnostics/reports").status_code == 200
    audits = owner_client.get("/api/v1/audit?action=diagnostics.viewed").json()
    assert audits


def test_retention_is_configurable_with_upper_limit(owner_client):
    owner_client.post("/api/v1/organizations", json={"name": "诊断设置组织"})
    response = owner_client.put(
        "/api/v1/diagnostics/settings",
        json={"enabled": True, "retentionDays": 365},
    )
    assert response.status_code == 200
    assert response.json()["retentionDays"] == 180


def test_expired_reports_are_cleaned(owner_client, tmp_path):
    owner_client.post("/api/v1/organizations", json={"name": "诊断清理组织"})
    owner_client.post("/api/v1/diagnostics/reports", json=valid_report())
    store = owner_client.app.state.report_store
    first = store.list()[0]
    store.save({**first, "retainUntil": time.time() - 1})
    assert owner_client.post("/api/v1/diagnostics/cleanup").json()["removed"] == 1
