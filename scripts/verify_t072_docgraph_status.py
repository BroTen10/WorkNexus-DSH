#!/usr/bin/env python
"""T-072 门禁：DocGraph 任务状态跟踪（P4-F04）。

断言：
  N1  轮询模块、任务列表页与测试齐备
  N2  插件测试与类型检查通过
  N3  五态齐备且未知状态映射为 unknown
  N4  有上限（maxPolls）与退避（backoffFactor / maxIntervalMs）
  N5  轮询失败不抛未捕获异常（降级为 unknown）
  N6  负向：无高频无退避轮询（默认间隔 ≥2s 且退避因子 >1）

用法：python scripts/verify_t072_docgraph_status.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "docgraph"
NODE = shutil.which("node")
STATES = ["queued", "running", "succeeded", "failed", "cancelled", "unknown"]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = ["src/status-poller.ts", "src/pages/JobList.tsx", "test/status-poller.test.ts"]
    missing = [item for item in need if not (PLUGIN / item).exists()]
    record(not missing, f"N1 结构齐备（缺: {missing or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
    record(test.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    poller = (PLUGIN / "src" / "status-poller.ts").read_text(encoding="utf-8")
    job_list = (PLUGIN / "src" / "pages" / "JobList.tsx").read_text(encoding="utf-8")
    tests = (PLUGIN / "test" / "status-poller.test.ts").read_text(encoding="utf-8")
    covered = [state for state in STATES if state in poller or state in job_list]
    record(len(covered) == 6 and "unknown" in poller,
           f"N3 五态 + unknown 齐备（覆盖: {', '.join(covered)}）")

    record(
        "maxPolls" in poller and "backoffFactor" in poller and "maxIntervalMs" in poller
        and "stops after maxPolls" in tests and "backs off between polls" in tests,
        "N4 有轮询上限与退避（含上限/退避用例）",
    )

    record(
        "catch {" in poller and "state = 'unknown'" in poller
        and "instead of throwing" in tests,
        "N5 轮询失败降级为 unknown，不抛未捕获异常",
    )

    record(
        "DEFAULT_POLL_INTERVAL_MS = 2000" in poller and "DEFAULT_BACKOFF_FACTOR = 1.5" in poller
        and "DEFAULT_MAX_INTERVAL_MS = 15000" in poller,
        "N6 默认间隔 2s、退避 1.5×、上限 15s（无高频无退避轮询）",
    )

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
