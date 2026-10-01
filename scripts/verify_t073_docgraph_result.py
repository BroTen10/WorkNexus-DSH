#!/usr/bin/env python
"""T-073 门禁：DocGraph 结果查看（P4-F05）。

断言：
  N1  结果视图与测试齐备
  N2  插件测试与类型检查通过
  N3  结构化 findings 渲染（规则/结论/严重度/说明）
  N4  三态 result 原样保留（pass / fail / unverifiable 不归一）
  N5  结构未知时回退原始 JSON，不空白
  N6  负向：不把正文写入本地存储（无 localStorage/sessionStorage/writeFile）

用法：python scripts/verify_t073_docgraph_result.py
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
PLUGIN = REPO / "plugins" / "docgraph"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    src = PLUGIN / "src" / "pages" / "JobResult.tsx"
    test = PLUGIN / "test" / "result.test.tsx"
    record(src.exists() and test.exists(),
           f"N1 结构齐备（缺: {[p.name for p in (src, test) if not p.exists()] or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test_run = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test_run.stdout.splitlines() if "Tests" in l]
    record(test_run.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test_run.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    code = src.read_text(encoding="utf-8")
    tests = test.read_text(encoding="utf-8")
    record(
        all(token in code for token in ("规则", "结论", "严重度", "说明"))
        and "findings" in code and "R1" in tests,
        "N3 结构化 findings 视图（规则/结论/严重度/说明）",
    )

    record(
        all(token in code for token in ("pass", "fail", "unverifiable"))
        and "不归一" in code
        and "['pass', 'fail', 'unverifiable']" in tests,
        "N4 三态 result 原样保留，不归一成二态",
    )

    record(
        "JSON.stringify(result" in code and "pre" in code and "falls back to raw JSON" in tests,
        "N5 结构未知时回退原始 JSON（不空白）",
    )

    stripped = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    hits = [token for token in ("localStorage", "sessionStorage", "writeFile", "fs.") if token in stripped]
    record(not hits, f"N6 不把正文写入本地存储（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
