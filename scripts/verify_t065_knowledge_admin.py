#!/usr/bin/env python
"""T-065 门禁：知识库管理页面（P3-F09）。

断言：
  N1  管理页面与测试齐备
  N2  插件测试与类型检查通过
  N3  manifest 声明两个官方 UI 槽位与 kb 权限
  N4  三项能力齐备（配置 Provider / 绑定空间 / 启停知识库）
  N5  模式门控与权限：个人模式零页面；非管理员零动作
  N6  负向：不新增插件管理 IPC、不引入第二套设计系统

用法：python scripts/verify_t065_knowledge_admin.py
"""

from __future__ import annotations

import json
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
    src = PLUGIN / "src" / "pages" / "KnowledgeAdmin.tsx"
    test = PLUGIN / "test" / "admin.test.tsx"
    record(src.exists() and test.exists(),
           f"N1 管理页面与测试齐备（缺: {[p.name for p in (src, test) if not p.exists()] or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test_run = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test_run.stdout.splitlines() if "Tests" in l]
    record(test_run.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test_run.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    manifest = json.loads((PLUGIN / "plugin.manifest.json").read_text(encoding="utf-8"))
    slots = manifest.get("uiSlots", [])
    record(
        {"worknexus.knowledge.connections", "worknexus.knowledge.admin"} <= set(slots)
        and {"kb.retrieve", "kb.bind"} <= set(manifest.get("permissions", [])),
        f"N3 official UI 槽位与 kb 权限齐备（槽位: {', '.join(slots)}）",
    )

    admin_src = src.read_text(encoding="utf-8")
    actions = ["configure-provider", "bind-space", "toggle-knowledge"]
    record(all(action in admin_src for action in actions),
           f"N4 三项能力齐备（{', '.join(actions)}）")

    admin_test = test.read_text(encoding="utf-8")
    record(
        "visiblePages('personal')" in admin_test
        and "adminActionsFor({ organizationId: 'o', role: 'member' })" in admin_test
        and "adminActionsFor({ organizationId: 'o', role: 'admin' })" in admin_test,
        "N5 模式门控与权限（个人模式零页面 / 非管理员零动作 / 管理员三动作）",
    )

    forbidden = ["ipcRenderer", "ipcMain", "installBundle", "antd", "@mui/material"]
    hits = [token for token in forbidden if token in admin_src]
    record(not hits, f"N6 无插件管理 IPC 与第二套设计系统（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
