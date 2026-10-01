#!/usr/bin/env python
"""T-081 门禁：IPD 样例流程视图（P5-F02 / P5-F03）。

断言：
  N1  视图与示例数据齐备
  N2  插件测试与类型检查通过
  N3  渲染阶段 / 评审点 / 交付物 / 角色四要素
  N4  页面显式标注「示例数据」，数据为少量本地静态样例
  N5  负向：不接真实数据源（无 fetch/axios/HTTP 调用）

用法：python scripts/verify_t081_ipd_process.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "ipd"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    src = PLUGIN / "src" / "pages" / "ProcessView.tsx"
    data = PLUGIN / "src" / "data" / "sample-process.json"
    test = PLUGIN / "test" / "process-view.test.tsx"
    missing = [path.name for path in (src, data, test) if not path.exists()]
    record(not missing, f"N1 结构齐备（缺: {missing or '无'}）")
    if missing or NODE is None:
        return finish()

    test_run = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test_run.stdout.splitlines() if "Tests" in l]
    record(test_run.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test_run.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    code = src.read_text(encoding="utf-8")
    record(
        all(token in code for token in ("阶段", "评审点", "交付物", "角色"))
        and "reviewPoint" in code and "deliverables" in code and "roles" in code,
        "N3 渲染阶段/评审点/交付物/角色四要素",
    )

    payload = json.loads(data.read_text(encoding="utf-8"))
    record(
        payload.get("demo") is True and payload.get("label") == "示例数据"
        and 1 <= len(payload.get("stages", [])) <= 5
        and all(stage.get("reviewPoint") and stage.get("deliverables") and stage.get("roles")
                for stage in payload.get("stages", [])),
        f"N4 显式示例标注且为少量静态数据（{len(payload.get('stages', []))} 个阶段）",
    )

    stripped = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    stripped = re.sub(r"(?m)^\s*//.*$", "", stripped)
    hits = [token for token in ("fetch(", "axios", "XMLHttpRequest", "http.request") if token in stripped]
    record(not hits, f"N5 不接真实数据源（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
