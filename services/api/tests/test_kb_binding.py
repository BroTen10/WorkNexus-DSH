"""T-063：知识库连接与空间绑定的控制面同源验证。"""


def _scaffold(client, name: str = "知识库组织"):
    org = client.post("/api/v1/organizations", json={"name": name}).json()
    dept = client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "研发部"}).json()
    space = client.post(
        f"/api/v1/departments/{dept['id']}/project-spaces",
        json={"name": "知识库空间"},
    ).json()
    return org, dept, space


def _create_kb(client, org_id: str, name: str = "研发知识库"):
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "organizationId": org_id,
            "name": name,
            "providerType": "http-rag",
            "endpointUrl": "http://rag.local:9380",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_binds_knowledge_base_to_project_space(owner_client):
    org, dept, space = _scaffold(owner_client)
    kb = _create_kb(owner_client, org["id"])
    assert kb["status"] == "active"

    binding = owner_client.post(
        "/api/v1/knowledge-bindings",
        json={"knowledgeBaseId": kb["id"], "projectSpaceId": space["id"], "weight": 3},
    ).json()
    assert binding["projectSpaceId"] == space["id"]
    assert binding["enabled"] is True
    assert binding["weight"] == 3

    listed = owner_client.get("/api/v1/knowledge-bindings", params={"organizationId": org["id"]}).json()
    assert [row["id"] for row in listed] == [binding["id"]]
    scoped = owner_client.get(
        "/api/v1/knowledge-bindings",
        params={"organizationId": org["id"], "projectSpaceId": space["id"]},
    ).json()
    assert [row["id"] for row in scoped] == [binding["id"]]
    other = owner_client.get(
        "/api/v1/knowledge-bindings",
        params={"organizationId": org["id"], "departmentId": dept["id"]},
    ).json()
    assert other == []

    audits = owner_client.get("/api/v1/audit").json()
    actions = [row["action"] for row in audits]
    assert "kb.create" in actions and "kb.bind" in actions


def test_binding_requires_exactly_one_scope(owner_client):
    org, dept, space = _scaffold(owner_client, "绑定范围组织")
    kb = _create_kb(owner_client, org["id"], "范围知识库")
    both = owner_client.post(
        "/api/v1/knowledge-bindings",
        json={"knowledgeBaseId": kb["id"], "departmentId": dept["id"], "projectSpaceId": space["id"]},
    )
    assert both.status_code == 400
    neither = owner_client.post("/api/v1/knowledge-bindings", json={"knowledgeBaseId": kb["id"]})
    assert neither.status_code == 400


def test_department_binding_is_allowed_and_duplicates_are_rejected(owner_client):
    org, dept, _ = _scaffold(owner_client, "部门绑定组织")
    kb = _create_kb(owner_client, org["id"], "部门知识库")
    payload = {"knowledgeBaseId": kb["id"], "departmentId": dept["id"]}
    assert owner_client.post("/api/v1/knowledge-bindings", json=payload).status_code == 200
    assert owner_client.post("/api/v1/knowledge-bindings", json=payload).status_code == 409


def test_non_admin_and_foreign_members_cannot_write(owner_client, member_client):
    org, dept, space = _scaffold(owner_client, "越权组织")
    kb = _create_kb(owner_client, org["id"], "越权知识库")
    assert member_client.post(
        "/api/v1/knowledge-bindings",
        json={"knowledgeBaseId": kb["id"], "projectSpaceId": space["id"]},
    ).status_code == 404
    assert member_client.post(
        "/api/v1/knowledge-bases",
        json={
            "organizationId": org["id"],
            "name": "越权连接",
            "providerType": "http-rag",
            "endpointUrl": "http://rag.local",
        },
    ).status_code == 404
    assert member_client.get(
        "/api/v1/knowledge-bindings", params={"organizationId": org["id"]}
    ).status_code == 404

    # 组织成员（非管理员）可读，但不可写
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    assert member_client.get(
        "/api/v1/knowledge-bases", params={"organizationId": org["id"]}
    ).status_code == 200
    assert member_client.post(
        "/api/v1/knowledge-bindings",
        json={"knowledgeBaseId": kb["id"], "departmentId": dept["id"]},
    ).status_code == 404


def test_cross_organization_scope_is_rejected(owner_client):
    org, _, space = _scaffold(owner_client, "跨组织A")
    other_org, other_dept, _ = _scaffold(owner_client, "跨组织B")
    kb = _create_kb(owner_client, org["id"], "跨组织知识库")
    assert owner_client.post(
        "/api/v1/knowledge-bindings",
        json={"knowledgeBaseId": kb["id"], "departmentId": other_dept["id"]},
    ).status_code == 404
    assert owner_client.get(
        "/api/v1/knowledge-bases", params={"organizationId": other_org["id"]}
    ).status_code == 200


def test_status_change_and_unbind_are_audited(owner_client):
    org, _, space = _scaffold(owner_client, "启停组织")
    kb = _create_kb(owner_client, org["id"], "启停知识库")
    binding = owner_client.post(
        "/api/v1/knowledge-bindings",
        json={"knowledgeBaseId": kb["id"], "projectSpaceId": space["id"]},
    ).json()

    disabled = owner_client.patch(f"/api/v1/knowledge-bases/{kb['id']}", json={"status": "disabled"})
    assert disabled.json()["status"] == "disabled"
    assert owner_client.patch(
        f"/api/v1/knowledge-bases/{kb['id']}", json={"status": "unknown"}
    ).status_code == 400

    removed = owner_client.delete(f"/api/v1/knowledge-bindings/{binding['id']}")
    assert removed.json() == {"id": binding["id"], "deleted": True}
    actions = [row["action"] for row in owner_client.get("/api/v1/audit").json()]
    assert "kb.update" in actions and "kb.unbind" in actions
