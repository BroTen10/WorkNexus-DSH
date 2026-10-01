#!/usr/bin/env python
"""T-104 门禁：安装审计与安全提示（P6B-F06、§4.6.2 验收 3）。

断言：
  N1  安全提示组件与测试齐备
  N2  插件测试与类型检查通过
  N3  展示权限、来源、最近更新与风险等级
  N4  风险规则 = 权限范围 + 来源可信度 + 更新时间（三项规则可判定）
  N5  安装/更新/启停审计齐备（plugin.install / plugin.update / plugin.enable / plugin.disable）
  N6  负向：不隐藏来源与权限（组件输出含来源与全部权限项）

用法：python scripts/verify_t104_risk_display.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
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
    need = [PLUGIN / "src" / "risk-display.tsx", PLUGIN / "test" / "risk-display.test.tsx"]
    missing = [path.name for path in need if not path.exists()]
    record(not missing, f"N1 结构齐备（缺: {missing or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
    record(test.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    src = (PLUGIN / "src" / "risk-display.tsx").read_text(encoding="utf-8")
    test_src = (PLUGIN / "test" / "risk-display.test.tsx").read_text(encoding="utf-8")
    record(
        all(token in src for token in ("permissions", "source", "lastUpdated", "风险等级"))
        and "shows permissions, source and last update" in test_src,
        "N3 展示权限/来源/最近更新与风险等级",
    )

    record(
        all(token in src for token in ("SENSITIVE_PERMISSIONS", "private-registry", "STALE_DAYS"))
        and "raises the risk level with sensitive permissions" in test_src,
        "N4 风险规则三项（权限范围 + 来源可信度 + 更新时间）均可判定",
    )

    audit_whitelist = (API / "app" / "services" / "audit.py").read_text(encoding="utf-8")
    router = (API / "app" / "routers" / "market_approval.py").read_text(encoding="utf-8")
    record(
        all(token in audit_whitelist for token in ('"plugin.install"', '"plugin.update"', '"plugin.enable"', '"plugin.disable"'))
        and '"plugin.install"' in router and '"plugin.update"' in router,
        "N5 安装/更新/启停审计齐备（白名单含四类动作；安装与更新由控制面写入）",
    )

    record(
        "worknexus-market-risk-source" in src and "worknexus-market-risk-permissions" in src
        and "keeps the source and permission list visible" in test_src,
        "N6 不隐藏来源与权限（来源与权限列表始终渲染）",
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
