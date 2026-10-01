#!/usr/bin/env python
"""T-050 门禁：企业管理插件 UI 声明与门控。

断言：
  N1  插件结构齐备
  N2  插件测试与类型检查通过
  N3  manifest 有六个官方 UI 槽位与权限
  N4  负向：不新增插件管理 IPC / 不实现第二套插件管理界面

用法：python scripts/verify_t050_admin_ui.py
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
PLUGIN = REPO / "plugins" / "enterprise-admin"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = ["package.json", "plugin.manifest.json", "cordis.patch.yml", "src/index.ts",
            "src/permissions.ts", "test/plugin.test.ts"]
    need += [f"src/pages/{name}.tsx" for name in
             ("Organizations", "Members", "Roles", "Spaces", "Audit", "Usage")]
    missing = [item for item in need if not (PLUGIN / item).exists()]
    record(not missing, f"N1 结构齐备（缺: {missing or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    record(test.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test.returncode}, typecheck={typecheck.returncode}）")

    manifest = json.loads((PLUGIN / "plugin.manifest.json").read_text(encoding="utf-8"))
    required_permissions = {"identity.read", "space.read", "audit.read", "usage.read", "budget.write"}
    record(
        len(manifest.get("uiSlots", [])) == 6
        and required_permissions <= set(manifest.get("permissions", []))
        and manifest.get("dsh", {}).get("bundle", {}).get("patch") == "./cordis.patch.yml",
        "N3 manifest 六槽位、权限与官方 bundle patch 齐备",
    )

    src = "\n".join((PLUGIN / "src" / f).read_text(encoding="utf-8") for f in ("index.ts", "permissions.ts"))
    tokens = [token for token in ("ipcRenderer", "ipcMain", "enablePlugin", "disablePlugin", "installBundle") if token in src]
    record(not tokens, f"N4 不新增插件管理 IPC / 启停能力（命中: {tokens or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
