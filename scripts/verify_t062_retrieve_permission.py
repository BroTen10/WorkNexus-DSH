#!/usr/bin/env python
"""T-062 门禁：检索前权限判定与检索后空间过滤（P3-F05）。

断言：
  N1  检索模块与测试齐备
  N2  插件测试与类型检查通过
  N3  无权限时不调用 Provider（实现顺序 + 测试断言双证据）
  N4  跨空间命中被丢弃（默认范围与显式绑定范围两种口径）
  N5  检索失败降级为空结果，不抛未捕获异常
  N6  负向：检索落点在企业插件内，不调用官方会话链路、不自行发起网络请求

用法：python scripts/verify_t062_retrieve_permission.py
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
PLUGIN = REPO / "plugins" / "knowledge"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    src = PLUGIN / "src" / "retrieve.ts"
    test = PLUGIN / "test" / "retrieve.test.ts"
    record(src.exists() and test.exists(), f"N1 检索模块与测试齐备（缺: {[p.name for p in (src, test) if not p.exists()] or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test_run = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test_run.stdout.splitlines() if "Tests" in l]
    record(test_run.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test_run.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    code = src.read_text(encoding="utf-8")
    test_code = test.read_text(encoding="utf-8")
    guard_index = code.find("policy.can(")
    provider_index = code.find("provider.retrieve(")
    record(
        -1 < guard_index < provider_index and "not.toHaveBeenCalled" in test_code,
        "N3 无权限时不调用 Provider（先 can 判定，再 retrieve；测试断言未被调用）",
    )

    record(
        "isChunkVisible" in code and "'other'" in test_code
        and "allowedSpaceIds" in code and "drops chunks bound to another project space" in test_code,
        "N4 跨空间命中被丢弃（默认范围 + 显式绑定允许集）",
    )

    record(
        "try {" in code and "catch" in code and "return []" in code
        and "provider exploded" in test_code,
        "N5 检索失败降级为空结果且不抛出",
    )

    stripped = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    stripped = re.sub(r"(?m)^\s*//.*$", "", stripped)
    hits = [token for token in ("fetch(", "kernel-dsh", "apps/desktop", "session.intercept") if token in stripped]
    record(not hits, f"N6 检索只落在企业插件内（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
