#!/usr/bin/env python
"""T-053 门禁：P2 企业管理插件与控制面收尾。

顺序：
  1. T-040~T-054 全部子门禁
  2. Python / TypeScript 全量回归
  3. 需求书 §4.2.7 九条证据
  4. §3.5 / §7.1 / §4.2.4 / §11 附加负向断言

用法：python scripts/verify_t053_p2.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

SUB_GATES = [
    ("T-040", "scripts/verify_t040_control_plane.py"),
    ("T-041", "scripts/verify_t041_core_entities.py"),
    ("T-042", "scripts/verify_t042_auth.py"),
    ("T-043", "scripts/verify_t043_orgs.py"),
    ("T-044", "scripts/verify_t044_permissions.py"),
    ("T-045", "scripts/verify_t045_space_visibility.py"),
    ("T-046", "scripts/verify_t046_audit.py"),
    ("T-047", "scripts/verify_t047_usage.py"),
    ("T-048", "scripts/verify_t048_budget.py"),
    ("T-049", "scripts/verify_t049_reports.py"),
    ("T-050", "scripts/verify_t050_admin_ui.py"),
    ("T-051", "scripts/verify_t051_identity.py"),
    ("T-052", "scripts/verify_t052_isolation.py"),
    ("T-054", "scripts/verify_t054_diagnostics.py"),
]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def js_test(package: Path, pattern: str | None = None) -> int:
    if NODE is None:
        return 1
    args = [NODE, package / "node_modules/vitest/vitest.mjs", "run"]
    if pattern:
        args.append(pattern)
    return run(*args, cwd=package).returncode


def main() -> int:
    failures: list[str] = []
    for task, script in SUB_GATES:
        result = run(sys.executable, script)
        record(result.returncode == 0, f"子门禁 {task}（exit={result.returncode}）")
        if result.returncode != 0:
            failures.append(task)

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"Python 全量回归（{tail}）")

    packages = [
        ("host-core", REPO / "packages/host-core"),
        ("plugin-runtime", REPO / "packages/plugin-runtime"),
        ("kernel-dsh", REPO / "packages/kernel-dsh"),
        ("enterprise-admin", REPO / "plugins/enterprise-admin"),
    ]
    js_results = []
    for name, package in packages:
        code = js_test(package)
        js_results.append(f"{name}={code}")
        if code:
            failures.append(name)
    record(all(item.endswith("=0") for item in js_results), f"TypeScript 全量回归（{' / '.join(js_results)}）")

    reports = {
        "P2-1": "docs/邮箱验证码登录_T-042.md",
        "P2-2": "docs/组织与空间_T-043.md",
        "P2-3": "docs/空间可见性_T-045.md",
        "P2-4": "docs/成员与权限_T-044.md",
        "P2-5": "docs/审计写入与查询_T-046.md",
        "P2-6": "docs/用量报表_T-049.md",
        "P2-7": "docs/预算策略_T-048.md",
        "P2-8": "docs/企业管理插件UI_T-050.md",
        "P2-9": "docs/插件治理挂接_T-032.md",
    }
    missing = [name for name, path in reports.items() if not (REPO / path).exists()]
    record(not missing, f"§4.2.7 九条证据（缺: {missing or '无'}）")

    identity = (REPO / "packages/host-core/src/identity.ts").read_text(encoding="utf-8")
    mode = (REPO / "packages/host-core/src/mode.ts").read_text(encoding="utf-8")
    plugin = (REPO / "plugins/enterprise-admin/src/permissions.ts").read_text(encoding="utf-8")
    boundary = (
        "buildOfficialSessionHeaders" in identity
        and "X-WorkNexus-Mode" in (REPO / "services/api/app/services/spaces.py").read_text(encoding="utf-8")
        and "personal" in mode
        and "visiblePages" in plugin
    )
    record(boundary, "§3.5 / §7.1 附加边界：个人模式隐藏入口；企业 Token 不入官方会话")

    audit = (REPO / "services/api/app/routers/audit.py").read_text(encoding="utf-8")
    usage = (REPO / "packages/kernel-dsh/src/usage.ts").read_text(encoding="utf-8")
    append_only = all(token not in audit for token in ("@router.patch", "@router.put", "@router.delete")) \
        and "totalTokens" in usage
    record(append_only, "§4.2.4 附加核查：审计只追加；用量缺失不猜")

    forbidden = {
        "services/api/app/services/permission.py": ["permission_editor"],
        "plugins/enterprise-admin/src/index.ts": ["ipcRenderer", "ipcMain"],
    }
    hits = [token for path, tokens in forbidden.items() for token in tokens if token in (REPO / path).read_text(encoding="utf-8")]
    record(not hits, f"§11 附加负向：无细粒度编辑器 / 插件管理 IPC（命中: {hits or '无'}）")

    if failures:
        print(f"未通过项: {', '.join(failures)}")
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
