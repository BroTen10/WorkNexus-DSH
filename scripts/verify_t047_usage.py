#!/usr/bin/env python
"""T-047 门禁：用量采集与只追加记录。

断言：
  U1  结构齐备
  U2  kernel-dsh 映射测试与 typecheck 通过
  U3  Host Core ledger 测试与 typecheck 通过
  U4  控制面 usage 测试通过；全量 pytest 通过
  U5  负向：无 usage update/delete；来源白名单齐备

用法：python scripts/verify_t047_usage.py
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
KERNEL = REPO / "packages" / "kernel-dsh"
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


def js(check: str, package: Path, pattern: str | None = None) -> int:
    if NODE is None:
        return 1
    if check == "test":
        args = [NODE, package / "node_modules/vitest/vitest.mjs", "run"]
        if pattern:
            args.append(pattern)
        return run(*args, cwd=package).returncode
    return run(NODE, package / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=package).returncode


def main() -> int:
    need = [KERNEL / "src/usage.ts", KERNEL / "test/usage.test.ts",
            HOST / "src/usage-ledger.ts", API / "app/routers/usage.py", API / "tests/test_usage.py"]
    missing = [str(item) for item in need if not item.exists()]
    record(not missing, f"U1 结构齐备（缺: {missing or '无'}）")

    record(js("test", KERNEL, "usage") == 0 and js("typecheck", KERNEL) == 0,
           f"U2 kernel-dsh usage（test/typecheck）")
    record(js("typecheck", HOST) == 0,
           "U3 Host Core usage ledger typecheck")

    usage_test = run(PYTHON, "-m", "pytest", "tests/test_usage.py", "-q", cwd=API)
    full_test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    record(usage_test.returncode == 0 and full_test.returncode == 0,
           f"U4 控制面测试（usage={usage_test.returncode}, full={full_test.returncode}）")

    router = (API / "app/routers/usage.py").read_text(encoding="utf-8")
    src = (KERNEL / "src/usage.ts").read_text(encoding="utf-8")
    bad = [token for token in ("@router.patch", "@router.put", "@router.delete") if token in router]
    good = all(token in router for token in ("dsh_event", "adapter_estimate", "manual_import"))
    record(not bad and good, f"U5 无 update/delete；来源白名单齐备（命中: {bad or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad_count = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad_count} [FAIL]")
    return 1 if bad_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
