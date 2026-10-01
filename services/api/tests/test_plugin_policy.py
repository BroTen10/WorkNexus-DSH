"""T-103：插件兼容性声明与版本锁定。"""

import pytest

from app.services import plugin_policy


def _org(owner_client, name: str = "版本策略组织"):
    return owner_client.post("/api/v1/organizations", json={"name": name}).json()


def test_plugin_must_declare_dsh_and_hostcore_compatibility(owner_client):
    org = _org(owner_client)
    response = owner_client.post(
        "/api/v1/market/whitelist",
        json={"organizationId": org["id"], "pluginId": "p", "version": "1.0.0"},
    )
    assert response.status_code == 422
    assert "dshCompatibility" in str(response.json())
    assert "hostCoreCompatibility" in str(response.json())


def test_incompatible_range_is_rejected(owner_client):
    org = _org(owner_client, "不兼容组织")
    response = owner_client.post(
        "/api/v1/market/whitelist",
        json={
            "organizationId": org["id"],
            "pluginId": "p",
            "version": "1.0.0",
            "dshCompatibility": ">=0.3.0 <0.4.0",
            "hostCoreCompatibility": ">=1.0.0",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "incompatible"
    assert any("dshCompatibility" in problem for problem in response.json()["detail"]["problems"])


def test_locked_version_is_not_auto_upgraded(owner_client):
    org = _org(owner_client, "锁定组织")
    owner_client.post(
        "/api/v1/market/whitelist",
        json={
            "organizationId": org["id"],
            "pluginId": "worknexus.knowledge",
            "version": "1.0.0",
            "dshCompatibility": ">=0.2.0-rc.1 <0.3.0",
            "hostCoreCompatibility": ">=1.0.0",
        },
    )
    locked = owner_client.post(
        "/api/v1/market/plugins/worknexus.knowledge/lock",
        json={"organizationId": org["id"], "version": "1.0.0"},
    ).json()
    assert locked["locked"] is True
    assert locked["lockedVersion"] == "1.0.0"

    upgrade = owner_client.post(
        "/api/v1/market/plugins/worknexus.knowledge/upgrade",
        json={"organizationId": org["id"], "targetVersion": "1.1.0"},
    )
    assert upgrade.status_code == 409
    assert upgrade.json()["detail"]["reason"] == "version_locked"

    actions = {row["action"] for row in owner_client.get("/api/v1/audit").json()}
    assert "market.version.lock" in actions


def test_unlocked_plugin_can_request_upgrade(owner_client):
    org = _org(owner_client, "可升级组织")
    owner_client.post(
        "/api/v1/market/whitelist",
        json={
            "organizationId": org["id"],
            "pluginId": "worknexus.ipd",
            "version": "1.0.0",
            "dshCompatibility": ">=0.2.0-rc.1 <0.3.0",
            "hostCoreCompatibility": ">=1.0.0",
        },
    )
    upgrade = owner_client.post(
        "/api/v1/market/plugins/worknexus.ipd/upgrade",
        json={"organizationId": org["id"], "targetVersion": "1.1.0"},
    )
    assert upgrade.status_code == 200
    assert upgrade.json()["delegatedTo"] == "@deepseek-ai/dsh-plugin-manager"


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("0.2.0-rc.1", "0.2.0", -1),
        ("0.2.0", "0.2.0-rc.1", 1),
        ("1.0.0", "1.0.0", 0),
        ("1.1.0", "1.0.0", 1),
        ("0.2.0-rc.2", "0.2.0-rc.1", 1),
    ],
)
def test_semver_comparison_handles_prerelease(left, right, expected):
    assert plugin_policy.compare_versions(left, right) == expected


def test_range_and_contract_constants_are_consistent():
    assert plugin_policy.version_in_range("0.2.0-rc.1", ">=0.2.0-rc.1 <0.3.0") is True
    assert plugin_policy.version_in_range("0.3.0", ">=0.2.0-rc.1 <0.3.0") is False
    assert plugin_policy.version_in_range("1.1.0", ">=1.0.0") is True
    assert plugin_policy.CONTRACT_VERSION == "1.1.0"
    assert plugin_policy.DSH_PINNED_VERSION == "0.2.0-rc.1"
