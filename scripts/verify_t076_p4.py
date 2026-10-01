#!/usr/bin/env python
"""T-076 门禁：P4 DocGraph Adapter 批次收尾（需求书 §4.4.4 五条）。

顺序：
  1. T-070~T-075 全部子门禁
  2. Python / TypeScript 全量回归
  3. 控制面端到端场景（提交 → 查看 → 取消 → 用量 → 审计）
  4. §4.4.4 五条验收证据指针
  5. 中断隔离：DocGraph 停止时 P2/P3 仍可用（回归证据）+ 插件侧降级断言
  6. §11 负向清单（不重构 DocGraph 核心、不做第二套会话/插件机制）

用法：python scripts/verify_t076_p4.py
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
PLUGIN = REPO / "plugins" / "docgraph"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

SUB_GATES = [
    ("T-070", "scripts/verify_t070_docgraph_client.py"),
    ("T-072", "scripts/verify_t072_docgraph_status.py"),
    ("T-073", "scripts/verify_t073_docgraph_result.py"),
    ("T-074", "scripts/verify_t074_docgraph_audit_usage.py"),
    ("T-075", "scripts/verify_t075_docgraph_agent.py"),
]

JS_PACKAGES = [
    ("contracts", REPO / "packages/contracts"),
    ("host-core", REPO / "packages/host-core"),
    ("plugin-runtime", REPO / "packages/plugin-runtime"),
    ("kernel-dsh", REPO / "packages/kernel-dsh"),
    ("enterprise-admin", REPO / "plugins/enterprise-admin"),
    ("knowledge", REPO / "plugins/knowledge"),
    ("docgraph", PLUGIN),
]

TASK_REPORTS = [
    "docs/DocGraph连接配置_T-070.md",
    "docs/DocGraph任务提交_T-071.md",
    "docs/DocGraph任务状态_T-072.md",
    "docs/DocGraph结果查看_T-073.md",
    "docs/DocGraph权限审计用量_T-074.md",
    "docs/DocGraph会话联动_T-075.md",
]

ACCEPTANCE_DOCS = {
    "P4-1": "docs/DocGraph连接配置_T-070.md",
    "P4-2": "docs/DocGraph任务提交_T-071.md",
    "P4-3": "docs/DocGraph结果查看_T-073.md",
    "P4-4": "docs/DocGraph权限审计用量_T-074.md",
    "P4-5": "docs/知识库插件_T-066.md",
}

E2E_PROGRAM = r"""
import json, os, tempfile
from fastapi.testclient import TestClient
from app.main import create_app


class Mailer:
    def __init__(self):
        self.sent = {}

    def send_code(self, email, code):
        self.sent[email] = code


tmp = tempfile.mkdtemp()
app = create_app(database_url='sqlite+pysqlite:///' + os.path.join(tmp, 'p4.db'))
mailer = Mailer()
app.state.email_sender = mailer
out = {}

with TestClient(app) as owner:
    owner.post('/api/v1/auth/code', json={'email': 'p4@example.com'})
    token = owner.post('/api/v1/auth/register', json={
        'email': 'p4@example.com', 'code': mailer.sent['p4@example.com'], 'password': 'S3cret!pass',
    }).json()['access_token']
    owner.headers.update({'Authorization': 'Bearer ' + token})
    org = owner.post('/api/v1/organizations', json={'name': 'P4 验收组织'}).json()
    dept = owner.post('/api/v1/organizations/' + org['id'] + '/departments', json={'name': '研发部'}).json()
    space = owner.post('/api/v1/departments/' + dept['id'] + '/project-spaces', json={'name': '审查空间'}).json()
    submit = owner.post('/api/v1/docgraph/tasks', json={
        'spaceId': space['id'], 'documentId': 'doc-1', 'contractId': 'contract-1',
    })
    job_id = submit.json().get('jobId')
    view = owner.get('/api/v1/docgraph/jobs/' + job_id)
    cancel = owner.post('/api/v1/docgraph/jobs/' + job_id + '/cancel')
    usage = owner.get('/api/v1/usage').json()
    audits = [row['action'] for row in owner.get('/api/v1/audit').json()]
    out['submit_status'] = submit.status_code
    out['job_id'] = job_id
    out['view_status'] = view.status_code
    out['cancel_status'] = cancel.status_code
    out['cancel_body'] = cancel.json()
    out['usage_docgraph'] = [row for row in usage['rows'] if row.get('pluginId') == 'docgraph']
    out['audits'] = audits
    # 中断隔离：业务无关的健康检查与知识库接口仍可用（P2/P3 不依赖 DocGraph）
    out['health'] = owner.get('/api/v1/health').json()
    out['knowledge_bases_status'] = owner.get(
        '/api/v1/knowledge-bases', params={'organizationId': org['id']}
    ).status_code
    out['enterprise_bindings_status'] = owner.get(
        '/api/v1/knowledge-bindings', params={'organizationId': org['id']}
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
        usage = data.get("usage_docgraph") or []
        ok = (
            data.get("submit_status") == 202
            and data.get("view_status") == 200
            and data.get("cancel_status") == 200
            and data.get("cancel_body", {}).get("status") == "cancelled"
            and data.get("cancel_body", {}).get("remoteSupported") is False
            and len(usage) == 1
            and usage[0].get("source") == "adapter_estimate"
            and usage[0].get("totalTokens") is None
            and {"docgraph.submit", "docgraph.view", "docgraph.cancel"} <= set(data.get("audits", []))
        )
        record(ok, "控制面端到端（提交/查看/取消/用量留空/三类审计）")

        isolation = (
            data.get("health", {}).get("database") == "up"
            and data.get("knowledge_bases_status") == 200
            and data.get("enterprise_bindings_status") == 200
        )
        record(isolation, "§4.4.4 第 4 条：DocGraph 不可用时 P2/P3 接口仍正常（真实调用）")

    reports = [path for path in TASK_REPORTS if not (REPO / path).exists()]
    record(not reports, f"T-070~T-075 交付说明齐备（缺: {reports or '无'}）")

    missing_acceptance = [name for name, path in ACCEPTANCE_DOCS.items() if not (REPO / path).exists()]
    record(not missing_acceptance, f"§4.4.4 五条验收证据指针（缺: {missing_acceptance or '无'}）")

    acceptance_test = (PLUGIN / "test" / "acceptance.test.tsx").read_text(encoding="utf-8")
    degrade = (
        "DocGraph 中断时降级" in acceptance_test
        and "toMatchObject({ ok: false })" in acceptance_test
        and "['unknown', 'unknown']" in acceptance_test
    )
    record(degrade, "§5.4 第 3 条：插件侧中断降级断言（健康不可用、轮询不崩）")

    import re

    raw_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PLUGIN / "src").rglob("*.ts")) + sorted((PLUGIN / "src").rglob("*.tsx"))
    )
    # 注释里会正当地出现「不实现 AgentTransport」这类表述，负向扫描只看实际代码
    source = re.sub(r"/\*.*?\*/", "", raw_source, flags=re.S)
    source = re.sub(r"(?m)^\s*//.*$", "", source)
    forbidden = [token for token in
                 ("AgentTransport", "ipcRenderer", "installBundle", "site-packages", "docgraph/backend",
                  "graph_service", "review_service.py")
                 if token in source]
    record(not forbidden, f"§11 负向清单：不重构 DocGraph 核心、无第二套会话/插件机制（命中: {forbidden or '无'}）")

    if failures:
        print(f"未通过项: {', '.join(failures)}")
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
