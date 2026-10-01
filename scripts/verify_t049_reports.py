#!/usr/bin/env python
"""T-049 门禁：用量报表。

断言：
  R1  结构齐备
  R2  pytest 全量通过
  R3  三维度与估算/精确分离字段存在
  R4  无数据维度显式 unknown，不填充 0

用法：python scripts/verify_t049_reports.py
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
    need = [API / "app/routers/reports.py", API / "tests/test_reports.py"]
    missing = [str(item) for item in need if not item.exists()]
    record(not missing, f"R1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"R2 pytest 退出码 {test.returncode}（{tail}）")

    src = (API / "app/routers/reports.py").read_text(encoding="utf-8")
    required = ['groupBy == "user"', 'groupBy == "space"', 'groupBy == "model"', '"estimated"', '"precise"']
    missing_tokens = [token for token in required if token not in src]
    record(not missing_tokens, f"R3 三维度与估算/精确分列（缺: {missing_tokens or '无'}）")

    bad = [token for token in ('"dimensionId": 0', '"totalTokens": 0,') if token in src]
    record('dimension_id = row.space_id or "unknown"' in src and not bad,
           f"R4 缺失维度显式 unknown（命中: {bad or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
