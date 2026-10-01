#!/usr/bin/env python
"""T-048 门禁：预算策略与硬阈值阻断。

断言：
  B1  结构齐备
  B2  pytest 全量通过
  B3  budget 模块包含三层 scope、软/硬阈值与明确 reason
  B4  负向：不把预算阻断伪装成网络错误

用法：python scripts/verify_t048_budget.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PYTHON = API / ".venv" / "Scripts" / "python.exe"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = [API / "app/services/budget.py", API / "app/routers/budget.py", API / "tests/test_budget.py"]
    missing = [str(item) for item in need if not item.exists()]
    record(not missing, f"B1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"B2 pytest 退出码 {test.returncode}（{tail}）")

    src = "\n".join((API / item).read_text(encoding="utf-8") for item in
                    ("app/services/budget.py", "app/routers/budget.py"))
    required = ["organization", "department", "project", "user", "soft", "hard", "budget_exceeded"]
    missing_tokens = [token for token in required if token not in src]
    record(not missing_tokens, f"B3 三层预算与阈值语义齐备（缺: {missing_tokens or '无'}）")

    bad = [token for token in ("network_error", "silent_block", "unknown_error") if token in src]
    record(not bad, f"B4 阻断原因明确，不伪装网络错误（命中: {bad or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad_count = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad_count} [FAIL]")
    return 1 if bad_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
