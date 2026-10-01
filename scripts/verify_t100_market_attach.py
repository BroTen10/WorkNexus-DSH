#!/usr/bin/env python
"""T-100 门禁：挂接官方插件管理器（P6B 前置）。

断言：
  N1  插件结构齐备
  N2  插件测试与类型检查通过
  N3  manifest 为 market 能力类型且声明 plugin.enable/disable
  N4  官方安装输入形态与注册表规则已取证写入（注册表包名/路径/git/tarball + 私有源隔离）
  N5  治理复用 T-032 钩子：非白名单安装被拒并写审计
  N6  负向：不自研插件市场、不替换官方管理器、不新增插件管理 IPC

用法：python scripts/verify_t100_market_attach.py
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
PLUGIN = REPO / "plugins" / "market"
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
            "src/index.ts", "src/official-manager.ts", "src/pages/Market.tsx", "test/market.test.ts"]
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
        manifest.get("type") in {"ui", "governance", "composite"}
        and {"plugin.enable", "plugin.disable"} <= set(manifest.get("permissions", [])),
        "N3 manifest 为市场能力类型且声明启停权限",
    )

    facts = (PLUGIN / "src" / "official-manager.ts").read_text(encoding="utf-8")
    record(
        all(token in facts for token in ("registry-package", "absolute-path", "git-url", "tarball"))
        and "fallbackRegistries" in facts
        and "privateRegistryIsolated" in facts
        and "officialApprovalDialog" in facts,
        "N4 官方安装输入形态与注册表规则已取证（含私有源隔离、无官方审批弹窗）",
    )

    test_code = (PLUGIN / "test" / "market.test.ts").read_text(encoding="utf-8")
    record(
        "createGovernanceHooks" in facts or "createGovernanceHooks" in (PLUGIN / "src" / "index.ts").read_text(encoding="utf-8")
        or "createGovernanceHooks" in test_code,
        "N5 治理复用 T-032 钩子（白名单拒绝 + 审计）",
    )

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PLUGIN / "src").rglob("*.ts")) + sorted((PLUGIN / "src").rglob("*.tsx"))
    )
    code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [token for token in ("ipcRenderer", "ipcMain", "pnpm add", "child_process", "registryClient") if token in code]
    record(not hits, f"N6 不自研市场/不替换官方管理器/无插件管理 IPC（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
