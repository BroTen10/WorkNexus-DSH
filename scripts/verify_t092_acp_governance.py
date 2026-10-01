#!/usr/bin/env python
"""T-092 门禁：ACP 权限、审计与用量（P6A 功能 4/5）。

断言：
  N1  路由增量、插件策略与测试齐备
  N2  控制面 pytest 全量通过
  N3  ACP 插件测试与类型检查通过
  N4  权限请求受策略/管理员确认约束（写类需管理员、只读自动放行、未知默认拒绝）
  N5  审计与用量落库：`acp.permission.request` 入审计、任务级用量记录（Token 留空）
  N6  负向：控制面与插件策略同形且都不放行未知工具；未授权 404 + denied 审计

用法：python scripts/verify_t092_acp_governance.py
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
PLUGIN = REPO / "plugins" / "acp"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    need = [API / "app" / "routers" / "jobs.py", API / "tests" / "test_acp_governance.py",
            PLUGIN / "src" / "approval.ts", PLUGIN / "test" / "approval.test.ts"]
    missing = [path.name for path in need if not path.exists()]
    record(not missing, f"N1 结构与测试齐备（缺: {missing or '无'}）")

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"N2 控制面 pytest（{tail}）")

    if NODE is not None:
        test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
        typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
        tail2 = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
        record(test.returncode == 0 and typecheck.returncode == 0,
               f"N3 ACP 插件测试/类型（test={test.returncode} {tail2[-1] if tail2 else ''}, typecheck={typecheck.returncode}）")
    else:
        record(False, "N3 node 不可用")

    router = (API / "app" / "routers" / "jobs.py").read_text(encoding="utf-8")
    approval = (PLUGIN / "src" / "approval.ts").read_text(encoding="utf-8")
    api_test = (API / "tests" / "test_acp_governance.py").read_text(encoding="utf-8")
    record(
        "permission-request" in router
        and all(token in router for token in ("POLICY_AUTO_ALLOWED_TOOLS", "POLICY_ADMIN_REQUIRED_TOOLS"))
        and all(token in api_test for token in ("requires_admin_approval", "policy.auto_allowed", "policy.default_deny")),
        "N4 权限请求受策略/管理员确认约束（三种判定各有用例）",
    )

    record(
        '"acp.permission.request"' in router
        and 'usage_id=f"acp:{row.id}"' in router
        and 'source="adapter_estimate"' in router
        and 'row["usageId"] == f"acp:{job[\'id\']}"' in api_test,
        "N5 审计与用量落库（任务级用量、Token 留空）",
    )

    same_policy = (
        all(token in approval for token in ("POLICY_AUTO_ALLOWED_TOOLS", "POLICY_ADMIN_REQUIRED_TOOLS"))
        and "policy.default_deny" in approval
        and "defaults to deny for unknown tools" in (PLUGIN / "test" / "approval.test.ts").read_text(encoding="utf-8")
    )
    record(same_policy and "result=\"denied\"" in router,
           "N6 客户端预判与控制面策略同形，未知工具默认拒绝；未授权写 denied 审计")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
