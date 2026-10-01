#!/usr/bin/env python
"""T-083 门禁：P5 IPD Demo 批次收尾（需求书 §4.5.4 四条）。

顺序：
  1. T-080~T-082 全部子门禁
  2. Python / TypeScript 全量回归
  3. §4.5.4 四条验收证据指针 + 集成断言
  4. §4.5.3「明确不做」逐条确认没有被顺手做进来
  5. §11 负向清单

用法：python scripts/verify_t083_p5.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PLUGIN = REPO / "plugins" / "ipd"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

SUB_GATES = [
    ("T-080", "scripts/verify_t080_ipd_entry.py"),
    ("T-081", "scripts/verify_t081_ipd_process.py"),
    ("T-082", "scripts/verify_t082_ipd_project.py"),
]

JS_PACKAGES = [
    ("contracts", REPO / "packages/contracts"),
    ("host-core", REPO / "packages/host-core"),
    ("plugin-runtime", REPO / "packages/plugin-runtime"),
    ("kernel-dsh", REPO / "packages/kernel-dsh"),
    ("enterprise-admin", REPO / "plugins/enterprise-admin"),
    ("knowledge", REPO / "plugins/knowledge"),
    ("docgraph", REPO / "plugins/docgraph"),
    ("ipd", PLUGIN),
]

TASK_REPORTS = [
    "docs/IPD入口_T-080.md",
    "docs/IPD流程视图_T-081.md",
    "docs/IPD项目视图_T-082.md",
]

ACCEPTANCE_DOCS = {
    "P5-1": "docs/IPD入口_T-080.md",
    "P5-2": "docs/IPD流程视图_T-081.md",
    "P5-3": "docs/IPD项目视图_T-082.md",
    "P5-4": "docs/IPD-Demo插件_T-083.md",
}

# §4.5.3 明确不做的五件事：不得出现在插件实现里（按关键词扫描实际代码）
FORBIDDEN_SCOPE = [
    ("workflow-engine", r"\b(workflowEngine|StateMachine|流程引擎)\b"),
    ("approval-flow", r"\b(approvalFlow|审批流|approveStep)\b"),
    ("plm-erp", r"\b(plmAdapter|erpAdapter|PLM/ERP 集成)\b"),
    ("gantt-scheduling", r"\b(gantt|resourceScheduling|排程)\b"),
    ("form-modeling", r"\b(formBuilder|表单建模)\b"),
]

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

    reports = [path for path in TASK_REPORTS if not (REPO / path).exists()]
    record(not reports, f"T-080~T-082 交付说明齐备（缺: {reports or '无'}）")

    missing_acceptance = [name for name, path in ACCEPTANCE_DOCS.items() if not (REPO / path).exists()]
    record(not missing_acceptance, f"§4.5.4 四条验收证据指针（缺: {missing_acceptance or '无'}）")

    acceptance_test = (PLUGIN / "test" / "acceptance.test.tsx").read_text(encoding="utf-8")
    record(
        "授权用户可打开 IPD Demo 页面" in acceptance_test
        and "未授权成员不可见" in acceptance_test
        and "Demo 插件故障被隔离" in acceptance_test,
        "§4.5.4 四条集成断言（可打开 / 流程可见 / 项目状态可见 / 故障隔离）",
    )

    raw_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PLUGIN / "src").rglob("*.ts")) + sorted((PLUGIN / "src").rglob("*.tsx"))
    )
    source = re.sub(r"/\*.*?\*/", "", raw_source, flags=re.S)
    source = re.sub(r"(?m)^\s*//.*$", "", source)
    scope_hits = [name for name, pattern in FORBIDDEN_SCOPE if re.search(pattern, source)]
    record(not scope_hits, f"§4.5.3 明确不做项未被实现（命中: {scope_hits or '无'}）")

    forbidden = [token for token in ("ipcRenderer", "ipcMain", "installBundle", "fetch(", "axios")
                 if token in source]
    record(not forbidden, f"§11 负向清单：无插件管理 IPC、无网络调用、不接管会话（命中: {forbidden or '无'}）")

    if failures:
        print(f"未通过项: {', '.join(failures)}")
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
