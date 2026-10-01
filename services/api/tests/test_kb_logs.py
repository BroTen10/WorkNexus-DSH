"""T-064：检索日志字段齐全、只追加、且不含查询正文。"""

import hashlib


def _scaffold(client, name: str = "日志组织"):
    org = client.post("/api/v1/organizations", json={"name": name}).json()
    dept = client.post(f"/api/v1/organizations/{org['id']}/departments", json={"name": "研发部"}).json()
    space = client.post(
        f"/api/v1/departments/{dept['id']}/project-spaces",
        json={"name": "日志空间"},
    ).json()
    kb = client.post(
        "/api/v1/knowledge-bases",
        json={
            "organizationId": org["id"],
            "name": f"{name}-知识库",
            "providerType": "http-rag",
            "endpointUrl": "http://rag.local:9380",
        },
    ).json()
    return org, dept, space, kb


def test_retrieval_log_records_required_fields_without_query_text(owner_client):
    org, _, space, kb = _scaffold(owner_client)
    query = "合同模板的违约责任条款"
    created = owner_client.post(
        "/api/v1/knowledge-retrieval-logs",
        json={
            "knowledgeBaseId": kb["id"],
            "query": query,
            "hitCount": 3,
            "durationMs": 128,
            "spaceId": space["id"],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["queryHash"] == hashlib.sha256(query.encode("utf-8")).hexdigest()
    assert body["queryLength"] == len(query)
    assert body["hitCount"] == 3 and body["durationMs"] == 128
    assert body["spaceId"] == space["id"] and body["userId"]
    assert body["retentionDays"] == 1095
    assert query not in created.text

    listed = owner_client.get("/api/v1/knowledge-retrieval-logs", params={"organizationId": org["id"]})
    assert listed.status_code == 200
    rows = listed.json()
    assert [row["id"] for row in rows] == [body["id"]]
    assert query not in listed.text
    assert "合同" not in listed.text

    filtered = owner_client.get(
        "/api/v1/knowledge-retrieval-logs",
        params={"organizationId": org["id"], "knowledgeBaseId": kb["id"]},
    ).json()
    assert [row["id"] for row in filtered] == [body["id"]]


def test_log_is_append_only_and_requires_admin_to_read(owner_client, member_client):
    org, _, space, kb = _scaffold(owner_client, "只追加组织")
    payload = {"knowledgeBaseId": kb["id"], "query": "只追加", "hitCount": 1, "durationMs": 5}
    created = owner_client.post("/api/v1/knowledge-retrieval-logs", json=payload).json()

    # 只追加：没有更新 / 删除接口
    assert owner_client.patch(f"/api/v1/knowledge-retrieval-logs/{created['id']}", json={}).status_code in (404, 405)
    assert owner_client.delete(f"/api/v1/knowledge-retrieval-logs/{created['id']}").status_code in (404, 405)

    # 非成员读写都是 404（不泄漏资源存在性）
    assert member_client.post("/api/v1/knowledge-retrieval-logs", json=payload).status_code == 404
    assert member_client.get(
        "/api/v1/knowledge-retrieval-logs", params={"organizationId": org["id"]}
    ).status_code == 404

    # 组织内普通成员可写（自己上报检索），但不能读取管理视图
    owner_client.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"email": "member@example.com", "role": "member"},
    )
    assert member_client.post(
        "/api/v1/knowledge-retrieval-logs",
        json={"knowledgeBaseId": kb["id"], "query": "成员检索", "hitCount": 2, "durationMs": 9, "spaceId": space["id"]},
    ).status_code == 200
    assert member_client.get(
        "/api/v1/knowledge-retrieval-logs", params={"organizationId": org["id"]}
    ).status_code == 404

    rows = owner_client.get("/api/v1/knowledge-retrieval-logs", params={"organizationId": org["id"]}).json()
    assert len(rows) == 2
    assert all(set(row) >= {"queryHash", "queryLength", "hitCount", "durationMs", "spaceId", "userId"} for row in rows)
