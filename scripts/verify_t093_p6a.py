#!/usr/bin/env python
"""T-093 门禁：P6A ACP 后台自动化批次收尾（需求书 §4.6.1）。

顺序：
  1. T-090~T-092 全部子门禁
  2. Python / TypeScript 全量回归
  3. 控制面端到端（创建 → 查看 → 取消 → 恢复 → 关闭 → 权限请求 → 审计与用量）
  4. §4.6.1 六项功能与四条验收证据指针
  5. 禁用隔离：ACP 不进入 P1~P5 主链路（负向扫描）

用法：python scripts/verify_t093_p6a.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PLUGIN = REPO / "plugins" / "acp"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

SUB_GATES = [
    ("T-090", "scripts/verify_t090_acp_transport.py"),
    ("T-091", "scripts/verify_t091_background_jobs.py"),
    ("T-092", "scripts/verify_t092_acp_governance.py"),
]

JS_PACKAGES = [
    ("contracts", REPO / "packages/contracts"),
    ("host-core", REPO / "packages/host-core"),
    ("plugin-runtime", REPO / "packages/plugin-runtime"),
    ("kernel-dsh", REPO / "packages/kernel-dsh"),
    ("enterprise-admin", REPO / "plugins/enterprise-admin"),
    ("knowledge", REPO / "plugins/knowledge"),
    ("docgraph", REPO / "plugins/docgraph"),
    ("ipd", REPO / "plugins/ipd"),
    ("acp", PLUGIN),
]

TASK_REPORTS = [
    "docs/ACP企业适配_T-090.md",
    "docs/后台任务管理_T-091.md",
    "docs/ACP治理_T-092.md",
]

ACCEPTANCE_DOCS = {
    "P6A-1": "docs/ACP企业适配_T-090.md",
    "P6A-2": "docs/后台任务管理_T-091.md",
    "P6A-3": "docs/后台任务管理_T-091.md",
    "P6A-4": "docs/ACP后台自动化_T-093.md",
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
app = create_app(database_url='sqlite+pysqlite:///' + os.path.join(tmp, 'p6a.db'))
mailer = Mailer()
app.state.email_sender = mailer
out = {}

with TestClient(app) as owner:
    owner.post('/api/v1/auth/code', json={'email': 'p6a@example.com'})
    token = owner.post('/api/v1/auth/register', json={
        'email': 'p6a@example.com', 'code': mailer.sent['p6a@example.com'], 'password': 'S3cret!pass',
    }).json()['access_token']
    owner.headers.update({'Authorization': 'Bearer ' + token})
    org = owner.post('/api/v1/organizations', json={'name': 'P6A 验收组织'}).json()
    dept = owner.post('/api/v1/organizations/' + org['id'] + '/departments', json={'name': '研发部'}).json()
    space = owner.post('/api/v1/departments/' + dept['id'] + '/project-spaces', json={'name': '自动化空间'}).json()

    created = owner.post('/api/v1/jobs', json={'spaceId': space['id'], 'kind': 'acp', 'inputSummary': '整理周报'})
    job_id = created.json().get('id')
    listed = owner.get('/api/v1/jobs')
    viewed = owner.get('/api/v1/jobs/' + job_id)
    cancelled = owner.post('/api/v1/jobs/' + job_id + '/cancel')
    resumed = owner.post('/api/v1/jobs/' + job_id + '/resume')
    closed = owner.post('/api/v1/jobs/' + job_id + '/close')
    permission = owner.post('/api/v1/jobs/' + job_id + '/permission-request', json={'tool': 'fs.write'})
    audits = [row['action'] for row in owner.get('/api/v1/audit').json()]
    usage = [row for row in owner.get('/api/v1/usage').json()['rows'] if row.get('pluginId') == 'acp']
    # 禁用隔离：P2/P3/P4 接口仍可用
    health = owner.get('/api/v1/health').json()
    knowledge = owner.get('/api/v1/knowledge-bases', params={'organizationId': org['id']}).status_code

    out['create_status'] = created.status_code
    out['job_id'] = job_id
    out['list_has_job'] = any(row['id'] == job_id for row in listed.json())
    out['view_status'] = viewed.status_code
    out['cancel'] = cancelled.json().get('status')
    out['resume'] = {'status': resumed.json().get('status'), 'resumes': resumed.json().get('resumes')}
    out['close'] = {'status': closed.json().get('status'), 'alreadyClosed': closed.json().get('alreadyClosed')}
    out['permission'] = {'status': permission.status_code, 'decidedBy': permission.json().get('decidedBy')}
    out['audits'] = audits
    out['usage'] = usage
    out['health'] = health
    out['knowledge_status'] = knowledge

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
        usage = data.get("usage") or []
        ok = (
            data.get("create_status") == 200
            and data.get("list_has_job") is True
            and data.get("view_status") == 200
            and data.get("cancel") == "cancelled"
            and data.get("resume", {}).get("status") == "queued"
            and data.get("resume", {}).get("resumes") == 1
            and data.get("close", {}).get("status") == "closed"
            and data.get("permission", {}).get("status") == 200
            and data.get("permission", {}).get("decidedBy") == "admin"
            and {"acp.job.start", "acp.job.cancel", "acp.job.resume", "acp.job.close",
                 "acp.permission.request"} <= set(data.get("audits", []))
            and len(usage) == 1
            and usage[0].get("totalTokens") is None
        )
        record(ok, "控制面端到端（创建/查看/取消/恢复/关闭/权限请求/审计/用量）")

        isolation = data.get("health", {}).get("database") == "up" and data.get("knowledge_status") == 200
        record(isolation, "§4.6.1 验收 4：ACP 相关接口存在时 P2/P3 仍正常（真实调用）")

    reports = [path for path in TASK_REPORTS if not (REPO / path).exists()]
    record(not reports, f"T-090~T-092 交付说明齐备（缺: {reports or '无'}）")

    missing_acceptance = [name for name, path in ACCEPTANCE_DOCS.items() if not (REPO / path).exists()]
    record(not missing_acceptance, f"§4.6.1 四条验收证据指针（缺: {missing_acceptance or '无'}）")

    acceptance_test = (PLUGIN / "test" / "acceptance.test.ts").read_text(encoding="utf-8")
    record(
        "任务生命周期与状态集合齐备" in acceptance_test
        and "权限请求受策略约束" in acceptance_test
        and "插件只用于后台自动化" in acceptance_test,
        "§4.6.1 四条集成断言（生命周期 / 策略 / 后台专用）",
    )

    transport = (REPO / "packages" / "kernel-dsh" / "src" / "acp-transport.ts").read_text(encoding="utf-8")
    router = (API / "app" / "routers" / "jobs.py").read_text(encoding="utf-8")
    main_chain = [token for token in ("session/intercept", "apps/desktop", "kernel-dsh/src/session")
                  if token in router]
    protocol = [token for token in ("jsonrpc", "spawn(", "createInterface")
                if token in re.sub(r"/\*.*?\*/", "", transport, flags=re.S)]
    record(not main_chain and not protocol,
           f"§4.6.1 第 6 条 / §11：ACP 不接管交互主链路、不自研协议（命中: {main_chain + protocol or '无'}）")

    if failures:
        print(f"未通过项: {', '.join(failures)}")
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
