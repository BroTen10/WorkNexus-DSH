#!/usr/bin/env python
"""T-052 门禁：插件治理与失败隔离自动化复跑。

场景映射：
  F1 插件启动抛错不阻断 Host Core
  F2 插件 UI 注册/渲染边界不阻断会话
  F3 控制面/外部服务异常有统一错误响应
  F4 禁用插件后入口停止注册
  F5 可选依赖缺失/失败时降级
  F6 内置 bundle 恢复与保护语义

用法：python scripts/verify_t052_isolation.py
"""

from __future__ import annotations

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
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    t023 = run(sys.executable, "scripts/verify_t023_bundle.py")
    record(t023.returncode == 0, "F1/F5/F6 启动失败、失败依赖降级与内置 bundle 保护（verify_t023_bundle）")

    if NODE is None:
        record(False, "F2 node 不可用")
    else:
        ui = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
        record(ui.returncode == 0, "F2 企业管理插件 UI 注册边界（plugin-enterprise-admin tests）")

    t040 = run(sys.executable, "scripts/verify_t040_control_plane.py")
    record(t040.returncode == 0, "F3 控制面健康与统一错误边界（verify_t040_control_plane）")

    t024 = run(sys.executable, "scripts/verify_t024_entries.py")
    record(t024.returncode == 0, "F4 禁用/个人模式后入口停止注册（verify_t024_entries）")

    t032 = run(sys.executable, "scripts/verify_t032_governance.py")
    record(t032.returncode == 0, "F4/F5 治理钩子异常不阻塞官方行为（verify_t032_governance）")

    t035 = run(sys.executable, "scripts/verify_t035_mode.py")
    record(t035.returncode == 0, "F2/F4 个人模式企业入口隐藏且官方会话能力保持（verify_t035_mode）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
