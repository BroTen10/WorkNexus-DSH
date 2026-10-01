#!/usr/bin/env python
"""T-106：把企业层打成 npm tarball 集，供上游桌面打包链消费。

为什么需要本脚本：上游 `prepare-package-set.ts` 只从**目录里的 tgz** 推导包集闭包
（`packedPackages(inputs)` 读每个 tarball 的 `package/package.json` 取包名与依赖键），
企业层不在上游 pnpm workspace 内，因此必须先在本仓库自行打包。

用法：
  python scripts/pack_enterprise.py
  python scripts/pack_enterprise.py --out .worknexus-packed

退出码：全部打包成功为 0；任一失败为 1。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
GLOBS = ("packages/*", "bundles/*", "plugins/*")


def pnpm() -> list[str]:
    for candidate in ("pnpm.cmd", "pnpm"):
        found = shutil.which(candidate)
        if found:
            return [found]
    return ["corepack", "pnpm"]


def member_dirs() -> list[Path]:
    dirs: list[Path] = []
    for pattern in GLOBS:
        for directory in sorted(REPO.glob(pattern)):
            if (directory / "package.json").exists():
                dirs.append(directory)
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".worknexus-packed")
    args = parser.parse_args()

    out = (REPO / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # 清掉旧 tarball，避免上一次的残留在包集闭包里被当成候选
    for stale in out.glob("*.tgz"):
        stale.unlink()

    members = member_dirs()
    if not members:
        print("[FAIL] 未找到任何企业包（packages/* bundles/* plugins/*）")
        return 1

    failures: list[str] = []
    for directory in members:
        manifest = json.loads((directory / "package.json").read_text(encoding="utf-8"))
        name = manifest.get("name", "?")
        proc = subprocess.run(
            [*pnpm(), "pack", "--pack-destination", str(out)],
            cwd=str(directory), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        # pnpm 的 stdout 末段包含产物路径（"Tarball Details" 之后的一行）。
        produced_path = next(
            (line.strip() for line in reversed(proc.stdout.splitlines()) if line.strip().endswith(".tgz")),
            "",
        )
        if proc.returncode != 0:
            failures.append(f"{name}: exit={proc.returncode} {proc.stderr.strip()[-200:]}")
            print(f"[FAIL] {name}")
        else:
            print(f"[OK] {name} → {Path(produced_path).name if produced_path else '?'}")

    produced = sorted(path.name for path in out.glob("*.tgz"))
    print("-" * 60)
    print(f"企业包目录: {out}")
    print(f"tarball 数: {len(produced)}（成员 {len(members)} 个）")
    if len(produced) != len(members):
        failures.append(f"tarball 数 {len(produced)} != 成员数 {len(members)}")
    if failures:
        print("失败项:" + "; ".join(failures))
        print(f"结果: 0 [OK] / {len(failures)} [FAIL]")
        return 1
    print(f"结果: {len(produced)} [OK] / 0 [FAIL]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
