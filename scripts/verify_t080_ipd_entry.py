#!/usr/bin/env python
"""T-080 门禁：IPD 入口与插件注册（P5-F01）。

断言：
  N1  插件结构齐备（官方 UI 插件形态）
  N2  插件测试与类型检查通过
  N3  manifest 为 `ui` 类型，声明三个官方槽位与 space.read
  N4  入口含菜单入口 + 项目空间入口（双挂载）
  N5  个人模式零入口、未授权角色不可见
  N6  负向：不做真实流程引擎、不新增插件管理 IPC

用法：python scripts/verify_t080_ipd_entry.py
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
    need = ["package.json", "plugin.manifest.json", "cordis.patch.yml", "tsconfig.json",
            "src/index.ts", "test/registration.test.ts"]
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

    manifest = json.loads((PLUGIN / "plugin.manifest.json").read_text(encoding="utf-8"))
    record(
        manifest.get("type") == "ui"
        and len(manifest.get("uiSlots", [])) == 3
        and "space.read" in manifest.get("permissions", [])
        and manifest.get("dsh", {}).get("bundle", {}).get("patch") == "./cordis.patch.yml",
        "N3 manifest 为 ui 类型且声明三个官方槽位与 space.read",
    )

    src = (PLUGIN / "src" / "index.ts").read_text(encoding="utf-8")
    record(
        "kind: 'menu'" in src and src.count("kind: 'project-space'") == 2,
        "N4 入口双挂载（菜单入口 + 两个项目空间入口）",
    )

    tests = (PLUGIN / "test" / "registration.test.ts").read_text(encoding="utf-8")
    record(
        "visibleEntries('personal')" in tests and "entriesForActor" in src
        and "hides all entries in personal mode" in tests,
        "N5 个人模式零入口；未授权角色零入口（复用 space.read）",
    )

    stripped = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    stripped = re.sub(r"(?m)^\s*//.*$", "", stripped)
    hits = [token for token in ("ipcRenderer", "ipcMain", "workflowEngine", "gantt", "plm", "erp")
            if re.search(rf"\b{token}\b", stripped)]
    record(not hits, f"N6 无插件管理 IPC、无真实流程引擎/PLM/ERP/甘特图（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
