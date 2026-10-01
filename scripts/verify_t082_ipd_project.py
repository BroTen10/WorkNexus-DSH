#!/usr/bin/env python
"""T-082 门禁：IPD 样例项目状态与 Agent 示例（P5-F04 / P5-F05）。

断言：
  N1  项目视图、示例数据、预置 prompt 与测试齐备
  N2  插件测试与类型检查通过
  N3  至少一个样例项目含当前阶段与阶段状态列表
  N4  预置 prompt 支持变量渲染，缺变量/未知模板显式报错
  N5  负向：不承诺真实流程自动化、不接真实业务数据源

用法：python scripts/verify_t082_ipd_project.py
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
    need = ["src/pages/ProjectView.tsx", "src/data/sample-projects.json", "src/prompts.ts",
            "test/project-view.test.tsx", "test/prompts.test.ts"]
    missing = [item for item in need if not (PLUGIN / item).exists()]
    record(not missing, f"N1 结构齐备（缺: {missing or '无'}）")
    if missing or NODE is None:
        return finish()

    test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
    record(test.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    payload = json.loads((PLUGIN / "src" / "data" / "sample-projects.json").read_text(encoding="utf-8"))
    projects = payload.get("projects", [])
    record(
        payload.get("demo") is True and payload.get("label") == "示例数据"
        and len(projects) >= 1
        and all(project.get("currentStage") and len(project.get("stages", [])) >= 2 for project in projects),
        f"N3 样例项目含当前阶段与阶段状态（{len(projects)} 个项目）",
    )

    prompts = (PLUGIN / "src" / "prompts.ts").read_text(encoding="utf-8")
    prompt_tests = (PLUGIN / "test" / "prompts.test.ts").read_text(encoding="utf-8")
    record(
        "{{" in prompts and "missing-variable" in prompts and "unknown-template" in prompts
        and "reports missing variables" in prompt_tests,
        "N4 预置 prompt 支持变量渲染，缺变量/未知模板显式报错",
    )

    stripped = re.sub(r"/\*.*?\*/", "", prompts, flags=re.S)
    stripped = re.sub(r"(?m)^\s*//.*$", "", stripped)
    project_src = (PLUGIN / "src" / "pages" / "ProjectView.tsx").read_text(encoding="utf-8")
    hits = [token for token in ("自动执行", "自动审批", "fetch(", "axios") if token in stripped or token in project_src]
    record(not hits, f"N5 不承诺自动化、不接真实数据源（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
