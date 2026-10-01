#!/usr/bin/env python
"""T-066 门禁：P3 知识库插件批次收尾（需求书 §4.3.4 六条）。

顺序：
  1. T-060~T-065 全部子门禁
  2. Python / TypeScript 全量回归
  3. 控制面端到端场景（连接 → 绑定 → 检索上报 → 非成员拒绝 → 日志无正文）
  4. §4.3.4 六条验收证据指针
  5. §11 负向清单（不做向量库/解析流水线、无第二套凭据与插件管理面）

用法：python scripts/verify_t066_p3.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PLUGIN = REPO / "plugins" / "knowledge"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

SUB_GATES = [
    ("T-060", "scripts/verify_t029_skeleton.py"),
    ("T-060", "scripts/verify_t034_contract_doc.py"),
    ("T-061", "scripts/verify_t061_knowledge_provider.py"),
    ("T-062", "scripts/verify_t062_retrieve_permission.py"),
    ("T-063", "scripts/verify_t063_kb_binding.py"),
    ("T-064", "scripts/verify_t064_citations_logs.py"),
    ("T-065", "scripts/verify_t065_knowledge_admin.py"),
]

JS_PACKAGES = [
    ("contracts", REPO / "packages/contracts"),
    ("host-core", REPO / "packages/host-core"),
    ("plugin-runtime", REPO / "packages/plugin-runtime"),
    ("kernel-dsh", REPO / "packages/kernel-dsh"),
    ("enterprise-admin", REPO / "plugins/enterprise-admin"),
    ("knowledge", PLUGIN),
]

ACCEPTANCE_DOCS = {
    "P3-1": "docs/知识库绑定_T-063.md",
    "P3-2": "docs/知识库检索权限_T-062.md",
    "P3-3": "docs/知识库检索权限_T-062.md",
    "P3-4": "docs/知识库引用与日志_T-064.md",
    "P3-5": "docs/插件失败隔离验证_T-052.md",
    "P3-6": "docs/知识库连接配置_T-061.md",
}

TASK_REPORTS = [
    "docs/知识库契约_T-060.md",
    "docs/知识库连接配置_T-061.md",
    "docs/知识库检索权限_T-062.md",
    "docs/知识库绑定_T-063.md",
    "docs/知识库引用与日志_T-064.md",
    "docs/知识库管理页面_T-065.md",
]

E2E_PROGRAM = r"""
import json, os, tempfile
from fastapi.testclient import TestClient
from app.main import create_app


class Mailer:
    def __init__(self):
        self.sent = {}

    def send_code(self, email, code):
        self.sent[email] = code


def register(client, mailer, email):
    client.post('/api/v1/auth/code', json={'email': email})
    response = client.post('/api/v1/auth/register', json={
        'email': email, 'code': mailer.sent[email], 'password': 'S3cret!pass',
    })
    response.raise_for_status()
    return response.json()['access_token']


tmp = tempfile.mkdtemp()
app = create_app(database_url='sqlite+pysqlite:///' + os.path.join(tmp, 'p3.db'))
mailer = Mailer()
app.state.email_sender = mailer
query = '合同模板'
out = {}

with TestClient(app) as owner:
    token = register(owner, mailer, 'p3-owner@example.com')
    owner.headers.update({'Authorization': 'Bearer ' + token})
    health = owner.get('/api/v1/health').json()
    org = owner.post('/api/v1/organizations', json={'name': 'P3 验收组织'}).json()
    dept = owner.post('/api/v1/organizations/' + org['id'] + '/departments', json={'name': '研发部'}).json()
    space = owner.post('/api/v1/departments/' + dept['id'] + '/project-spaces', json={'name': '知识库空间'}).json()
    kb = owner.post('/api/v1/knowledge-bases', json={
        'organizationId': org['id'], 'name': 'P3 知识库', 'providerType': 'http-rag',
        'endpointUrl': 'http://rag.local:9380',
    }).json()
    binding = owner.post('/api/v1/knowledge-bindings', json={
        'knowledgeBaseId': kb['id'], 'projectSpaceId': space['id'], 'weight': 1,
    }).json()
    created = owner.post('/api/v1/knowledge-retrieval-logs', json={
        'knowledgeBaseId': kb['id'], 'query': query, 'hitCount': 2, 'durationMs': 42,
        'spaceId': space['id'],
    })
    listed = owner.get('/api/v1/knowledge-retrieval-logs', params={'organizationId': org['id']})
    audits = [row['action'] for row in owner.get('/api/v1/audit').json()]
    out['health'] = health
    out['binding_space'] = binding.get('projectSpaceId')
    out['binding_enabled'] = binding.get('enabled')
    out['log_status'] = created.status_code
    out['log_query_length'] = created.json().get('queryLength')
    out['log_count'] = len(listed.json())
    out['query_leaked'] = query in listed.text
    out['audits'] = audits
    out['org_id'] = org['id']
    out['kb_id'] = kb['id']

    outsider = TestClient(app)
    outsider_token = register(outsider, mailer, 'p3-outsider@example.com')
    outsider.headers.update({'Authorization': 'Bearer ' + outsider_token})
    out['outsider_write'] = outsider.post('/api/v1/knowledge-retrieval-logs', json={
        'knowledgeBaseId': kb['id'], 'query': 'x', 'hitCount': 0, 'durationMs': 1,
    }).status_code
    out['outsider_read'] = outsider.get(
        '/api/v1/knowledge-retrieval-logs', params={'organizationId': org['id']}
    ).status_code

print(json.dumps(out, ensure_ascii=False))
"""

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def js_test(package: Path) -> int:
    if NODE is None:
        return 1
    return run(NODE, package / "node_modules/vitest/vitest.mjs", "run", cwd=package).returncode


def main() -> int:
    failures: list[str] = []
    for task, script in SUB_GATES:
        result = run(sys.executable, script)
        record(result.returncode == 0, f"子门禁 {task} / {Path(script).name}（exit={result.returncode}）")
        if result.returncode != 0:
            failures.append(script)

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"Python 全量回归（{tail}）")

    js_results = []
    for name, package in JS_PACKAGES:
        code = js_test(package)
        js_results.append(f"{name}={code}")
        if code:
            failures.append(name)
    record(all(item.endswith("=0") for item in js_results),
           f"TypeScript 全量回归（{' / '.join(js_results)}）")

    e2e = run(PYTHON, "-c", E2E_PROGRAM, cwd=API)
    try:
        data = json.loads((e2e.stdout or "").strip().splitlines()[-1])
    except Exception:
        data = {}
        record(False, f"控制面端到端（解析失败: {(e2e.stdout or e2e.stderr or '').strip()[:160]}）")
    if data:
        ok = (
            data.get("health", {}).get("database") == "up"
            and data.get("binding_space")
            and data.get("binding_enabled") is True
            and data.get("log_status") == 200
            and data.get("log_query_length") == 4
            and data.get("log_count") == 1
            and data.get("query_leaked") is False
            and data.get("outsider_write") == 404
            and data.get("outsider_read") == 404
            and "kb.create" in data.get("audits", [])
            and "kb.bind" in data.get("audits", [])
        )
        record(ok, "控制面端到端（健康/绑定/检索上报/非成员 404/日志无正文/审计）")

    reports = [path for path in TASK_REPORTS if not (REPO / path).exists()]
    record(not reports, f"T-060~T-065 交付说明齐备（缺: {reports or '无'}）")

    acceptance = ACCEPTANCE_DOCS
    missing_acceptance = [name for name, path in acceptance.items() if not (REPO / path).exists()]
    record(not missing_acceptance,
           f"§4.3.4 六条验收证据指针（缺: {missing_acceptance or '无'}）")

    acceptance_test = (PLUGIN / "test" / "acceptance.test.tsx").read_text(encoding="utf-8")
    degrade = (
        "不可用时降级" in acceptance_test
        and "expect(chunks).toEqual([])" in acceptance_test
        and "not.toHaveBeenCalled" in acceptance_test
    )
    record(degrade, "§4.3.4 第 3/6 条集成断言：非成员不调用 Provider、Provider 不可用降级为空")

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PLUGIN / "src").rglob("*.ts")) + sorted((PLUGIN / "src").rglob("*.tsx"))
    )
    forbidden = [token for token in
                 ("embedding", "vectorStore", "chroma", "milvus", "ipcRenderer", "installBundle",
                  "Keychain", "kernel-dsh", "apps/desktop")
                 if token in source]
    record(not forbidden, f"§11 负向清单：无自研向量库/解析流水线、无第二套凭据与插件管理面（命中: {forbidden or '无'}）")

    if failures:
        print(f"未通过项: {', '.join(failures)}")
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
