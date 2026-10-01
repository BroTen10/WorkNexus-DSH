#!/usr/bin/env python
"""T-105 门禁：P6B 插件市场与企业治理批次收尾（需求书 §4.6.2，全计划最后一批）。

顺序：
  1. T-100~T-104 全部子门禁
  2. Python / TypeScript 全量回归
  3. 控制面端到端（私有源配置 → 未白名单被拦 → 审批 → 安装放行 → 锁定 → 升级被拒）
  4. §4.6.2 六项功能与四条验收证据指针
  5. §11 负向清单（不自研插件市场）+ 个人/企业模式差异

用法：python scripts/verify_t105_p6b.py
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
PLUGIN = REPO / "plugins" / "market"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

SUB_GATES = [
    ("T-100", "scripts/verify_t100_market_attach.py"),
    ("T-101", "scripts/verify_t101_private_source.py"),
    ("T-102", "scripts/verify_t102_market_approval.py"),
    ("T-103", "scripts/verify_t103_plugin_policy.py"),
    ("T-104", "scripts/verify_t104_risk_display.py"),
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
    ("acp", REPO / "plugins/acp"),
    ("market", PLUGIN),
]

TASK_REPORTS = [
    "docs/插件市场挂接_T-100.md",
    "docs/私有插件源_T-101.md",
    "docs/插件白名单与审批_T-102.md",
    "docs/插件版本锁定_T-103.md",
    "docs/插件安装审计与提示_T-104.md",
]

ACCEPTANCE_DOCS = {
    "P6B-1": "docs/插件市场挂接_T-100.md",
    "P6B-2": "docs/插件白名单与审批_T-102.md",
    "P6B-3": "docs/插件安装审计与提示_T-104.md",
    "P6B-4": "docs/私有插件源_T-101.md",
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
app = create_app(database_url='sqlite+pysqlite:///' + os.path.join(tmp, 'p6b.db'))
mailer = Mailer()
app.state.email_sender = mailer
out = {}

with TestClient(app) as owner:
    owner.post('/api/v1/auth/code', json={'email': 'p6b@example.com'})
    token = owner.post('/api/v1/auth/register', json={
        'email': 'p6b@example.com', 'code': mailer.sent['p6b@example.com'], 'password': 'S3cret!pass',
    }).json()['access_token']
    owner.headers.update({'Authorization': 'Bearer ' + token})
    org = owner.post('/api/v1/organizations', json={'name': 'P6B 验收组织'}).json()

    registry = owner.post('/api/v1/market/registry', json={
        'organizationId': org['id'], 'baseUrl': 'https://registry.corp.local', 'timeoutMs': 2000,
    })
    blocked = owner.post('/api/v1/market/install', json={
        'pluginId': 'third.party.plugin', 'organizationId': org['id'],
    })
    missing_decl = owner.post('/api/v1/market/whitelist', json={
        'organizationId': org['id'], 'pluginId': 'third.party.plugin', 'version': '1.0.0',
    })
    approval = owner.post('/api/v1/market/approvals', json={
        'organizationId': org['id'], 'pluginId': 'third.party.plugin', 'version': '1.0.0', 'action': 'install',
    }).json()
    decided = owner.post('/api/v1/market/approvals/' + approval['id'] + '/decision', json={
        'decision': 'approved', 'reason': '已评估',
    })
    owner.post('/api/v1/market/whitelist', json={
        'organizationId': org['id'], 'pluginId': 'third.party.plugin', 'version': '1.0.0',
        'dshCompatibility': '>=0.2.0-rc.1 <0.3.0', 'hostCoreCompatibility': '>=1.0.0',
    })
    installed = owner.post('/api/v1/market/install', json={
        'pluginId': 'third.party.plugin', 'organizationId': org['id'],
    })
    locked = owner.post('/api/v1/market/plugins/third.party.plugin/lock', json={
        'organizationId': org['id'], 'version': '1.0.0',
    })
    upgrade = owner.post('/api/v1/market/plugins/third.party.plugin/upgrade', json={
        'organizationId': org['id'], 'targetVersion': '1.1.0',
    })
    personal = owner.post('/api/v1/market/install', json={
        'pluginId': 'personal.only.plugin', 'organizationId': org['id'], 'mode': 'personal',
    })
    audits = [row['action'] for row in owner.get('/api/v1/audit').json()]

    out['registry_status'] = registry.status_code
    out['blocked'] = {'status': blocked.status_code, 'reason': blocked.json().get('detail', {}).get('reason')}
    out['missing_decl_status'] = missing_decl.status_code
    out['decision'] = decided.json().get('status')
    out['installed'] = {'status': installed.status_code, 'delegatedTo': installed.json().get('delegatedTo')}
    out['locked'] = {'status': locked.status_code, 'locked': locked.json().get('locked')}
    out['upgrade'] = {'status': upgrade.status_code, 'reason': upgrade.json().get('detail', {}).get('reason')}
    out['personal'] = {'status': personal.status_code, 'enforced': personal.json().get('enforced')}
    out['audits'] = audits

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
            data.get("registry_status") == 200
            and data.get("blocked", {}).get("status") == 403
            and data.get("blocked", {}).get("reason") == "not_whitelisted"
            and data.get("missing_decl_status") == 422
            and data.get("decision") == "approved"
            and data.get("installed", {}).get("status") == 200
            and data.get("installed", {}).get("delegatedTo") == "@deepseek-ai/dsh-plugin-manager"
            and data.get("locked", {}).get("locked") is True
            and data.get("upgrade", {}).get("status") == 409
            and data.get("upgrade", {}).get("reason") == "version_locked"
            and data.get("personal", {}).get("enforced") is False
            and {"market.registry.update", "market.whitelist.update", "market.approval.request",
                 "market.approval.decide", "plugin.install", "market.version.lock"} <= set(data.get("audits", []))
        )
        record(ok, "控制面端到端（私有源/拦截/审批/安装/锁定/升级拒绝/个人模式/审计）")

    reports = [path for path in TASK_REPORTS if not (REPO / path).exists()]
    record(not reports, f"T-100~T-104 交付说明齐备（缺: {reports or '无'}）")

    missing_acceptance = [name for name, path in ACCEPTANCE_DOCS.items() if not (REPO / path).exists()]
    record(not missing_acceptance, f"§4.6.2 四条验收证据指针（缺: {missing_acceptance or '无'}）")

    acceptance_test = (PLUGIN / "test" / "acceptance.test.tsx").read_text(encoding="utf-8")
    record(
        "市场入口走官方表面" in acceptance_test
        and "企业模式未白名单被拦" in acceptance_test
        and "私有源不可达时降级" in acceptance_test
        and "只通过官方能力面驱动安装" in acceptance_test,
        "§4.6.2 四条集成断言（官方表面 / 白名单 / 私有源降级 / 官方能力面）",
    )

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PLUGIN / "src").rglob("*.ts")) + sorted((PLUGIN / "src").rglob("*.tsx"))
    )
    code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [token for token in ("ipcRenderer", "child_process", "pnpm add", "dshmarket") if token in code]
    record(not hits, f"§11 负向清单：不自研插件市场/不引 dshmarket/无插件管理 IPC（命中: {hits or '无'}）")

    if failures:
        print(f"未通过项: {', '.join(failures)}")
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
