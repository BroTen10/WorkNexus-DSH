#!/usr/bin/env python
"""T-044 门禁：成员、角色与权限矩阵。

断言：
  P1  结构齐备
  P2  Python 矩阵测试通过
  P3  Host Core 客户端测试与类型检查通过
  P4  矩阵覆盖四类角色；服务端权限模块无细粒度编辑器

用法：python scripts/verify_t044_permissions.py
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
HOST = REPO / "packages" / "host-core"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = [API / "app/services/permission.py", API / "app/routers/members.py",
            API / "tests/test_permission_matrix.py", REPO / "packages/host-core/src/permission-client.ts",
            REPO / "packages/host-core/test/permission-client.test.ts"]
    missing = [str(item) for item in need if not item.exists()]
    record(not missing, f"P1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests/test_permission_matrix.py", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"P2 Python 矩阵测试退出码 {test.returncode}（{tail}）")

    if NODE is None:
        record(False, "P3 Host Core 测试/类型（node 不可用）")
        return finish()
    js_test = run(NODE, HOST / "node_modules/vitest/vitest.mjs", "run", "permission-client", cwd=HOST)
    js_type = run(NODE, HOST / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=HOST)
    record(js_test.returncode == 0 and js_type.returncode == 0,
           f"P3 Host Core 测试/类型（test={js_test.returncode}, typecheck={js_type.returncode}）")

    probe = run(PYTHON, "-c", "from app.services.permission import matrix_is_complete; print(matrix_is_complete())", cwd=API)
    src = (API / "app/services/permission.py").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    tokens = [token for token in ("permission_editor", "custom_action", "grant_action") if token in code]
    record(probe.stdout.strip() == "True" and not tokens,
           f"P4 矩阵完整且无细粒度编辑器（matrix={probe.stdout.strip()}，命中: {tokens or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
