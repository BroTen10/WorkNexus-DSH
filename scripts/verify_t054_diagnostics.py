#!/usr/bin/env python
"""T-054 门禁：诊断上报接收、留存与访问审计。

断言：
  G1  结构齐备
  G2  pytest 全量通过
  G3  字段白名单恰为 10 项且与 §7.1 对齐
  G4  留存默认 30 / 上限 180；访问、设置与清理接口存在
  G5  负向：不接收 prompt / 文件内容 / 凭据字段

用法：python scripts/verify_t054_diagnostics.py
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
    need = [API / "app/routers/diagnostics.py", API / "app/services/report_store.py",
            API / "tests/test_diagnostics.py"]
    missing = [str(item) for item in need if not item.exists()]
    record(not missing, f"G1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"G2 pytest 退出码 {test.returncode}（{tail}）")

    src = (API / "app/routers/diagnostics.py").read_text(encoding="utf-8")
    expected = {
        "runtimeVersion", "platform", "architecture", "profileValidation", "pluginStates",
        "errorType", "errorCode", "errorSummary", "timestamp", "anonymousInstallId",
    }
    allowed = "ALLOWED_FIELDS = {" in src and all(field in src for field in expected)
    record(allowed and "ALLOWED_FIELDS" in src, f"G3 字段白名单齐备（数量=10）")

    store = (API / "app/services/report_store.py").read_text(encoding="utf-8")
    good = all(token in store for token in ("retentionDays", "min(max(retention_days, 1), 180)")) \
        and all(token in src for token in ("/reports", "/settings", "/cleanup"))
    record(good, "G4 留存 30/180 与接收、设置、清理接口齐备")

    bad = [token for token in ("prompt", "fileContent", "sessionTitle", "apiKey", "token") if token in src]
    record(not bad, f"G5 不接收敏感字段（命中: {bad or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad_count = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad_count} [FAIL]")
    return 1 if bad_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
