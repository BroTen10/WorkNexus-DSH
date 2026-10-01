#!/usr/bin/env python
"""企业发行版 Windows 未签名出包入口（固化出网镜像）。

为什么需要本脚本：出包序列有**两处** GitHub 下载点，任一不可达都会让整条命令中断（2026-09-30 实测
两次中断）：
  1. `prepare:runtime` 经 `@electron/get` 取 Electron 二进制（`github.com`）→ 环境变量 `ELECTRON_MIRROR`；
  2. `electron-builder` 取自己的工具集 nsis / nsis-resources / winCodeSign / icons
     （`release-assets.githubusercontent.com`）→ 环境变量 `ELECTRON_BUILDER_BINARIES_MIRROR`。
上游 `.env.windows` 对键有**严格白名单**（未知键直接报 `desktop package: unsupported setting ...`），
放不下这两个设置；macOS 模板另有 `DSH_DESKTOP_MACOS_DOWNLOAD_PROXY`，Windows 侧没有同类键。
因此 Windows 侧唯一可用杠杆是**进程环境变量**，本脚本把两者一起固化，避免每次手工设置或漏设。

镜像布局（已实测可用，`<镜像>/<releaseName>/<文件名>`）：
  electron：`https://npmmirror.com/mirrors/electron/v<version>/electron-v<version>-win32-x64.zip`
  builder 工具集：`https://npmmirror.com/mirrors/electron-builder-binaries/{nsis-3.0.4.1/nsis-3.0.4.1.7z,
  nsis-resources-3.4.1/…, winCodeSign-2.6.0/…, icons@1.1.0/icons-bundle.tar.gz}`

用法：
  python scripts/package_desktop_win_unsigned.py                      # 默认 npmmirror 镜像
  python scripts/package_desktop_win_unsigned.py --dry-run            # 只打印将要执行的命令
  python scripts/package_desktop_win_unsigned.py --electron-mirror <url>
  python scripts/package_desktop_win_unsigned.py --electron-builder-mirror <url>
  python scripts/package_desktop_win_unsigned.py --no-mirror          # 不注入，走上游默认 github

前置：`python scripts/pack_enterprise.py`（企业层 tgz）与本地 `apps/desktop/.env.windows`。
退出码：与上游打包命令一致（0 为成功）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
ENV_FILE = UPSTREAM / "apps" / "desktop" / ".env.windows"
PACKED = REPO / ".worknexus-packed"
PACKAGE_SCRIPT = "package:desktop:win:x64:unsigned"

# 默认镜像：与 2026-09-30 实测可用的一致；可由 --electron-mirror 或已存在的环境变量覆盖。
DEFAULT_ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
DEFAULT_BUILDER_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"


def pnpm() -> list[str]:
    for candidate in ("pnpm.cmd", "pnpm"):
        found = shutil.which(candidate)
        if found:
            return [found]
    return ["corepack", "pnpm"]


def resolve_mirror(explicit: str | None, env_name: str, default: str, disabled: bool) -> str | None:
    if disabled:
        return None
    if explicit:
        return explicit
    inherited = os.environ.get(env_name)
    return inherited if inherited else default


def main() -> int:
    ap = argparse.ArgumentParser(description="企业发行版 Windows 未签名出包（含出网镜像固化）")
    ap.add_argument("--electron-mirror", default=None,
                    help=f"Electron 下载镜像；默认 {DEFAULT_ELECTRON_MIRROR}")
    ap.add_argument("--electron-builder-mirror", default=None,
                    help=f"electron-builder 工具集镜像；默认 {DEFAULT_BUILDER_MIRROR}")
    ap.add_argument("--no-mirror", action="store_true", help="不注入 ELECTRON_MIRROR（走上游默认 github）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要执行的命令与探活结果")
    args = ap.parse_args()

    # ── 探活（先检查前置，再执行，避免跑到一半才失败）──
    problems: list[str] = []
    if not (UPSTREAM / "package.json").is_file():
        problems.append(f"上游 fork 缺失: {UPSTREAM}")
    if not ENV_FILE.is_file():
        problems.append(f"缺少 {ENV_FILE}（先运行 python scripts/provision_t022_update_env.py 或按 "
                        f"{ENV_FILE}.example 填写）")
    tarballs = sorted(PACKED.glob("*.tgz")) if PACKED.is_dir() else []
    if not tarballs:
        problems.append(f"企业层包集为空: {PACKED}（先运行 python scripts/pack_enterprise.py）")

    mirror = resolve_mirror(args.electron_mirror, "ELECTRON_MIRROR", DEFAULT_ELECTRON_MIRROR, args.no_mirror)
    builder_mirror = resolve_mirror(args.electron_builder_mirror, "ELECTRON_BUILDER_BINARIES_MIRROR",
                                    DEFAULT_BUILDER_MIRROR, args.no_mirror)
    # 只改本进程的 os.environ，并让子进程**继承原始环境块**（不传 env=）。
    # 原因：CPython 在 Windows 上把 os.environ 的键大写化（ProgramFiles(x86) → PROGRAMFILES(X86)）。
    # 上游 package-target 会把 process.env 展开成普通对象再精确取 `environment['ProgramFiles(x86)']`
    # （普通对象没有 Node 的大小写不敏感查找），键一旦被大写化，宿主机预检就会报
    # `vswhere: ProgramFiles(x86) is not set, so Visual Studio cannot be located`。
    # 实测（2026-09-30）：传 env=dict(os.environ) 会被大写化并失败；不传 env= 则原始大小写保留。
    for name, value in (("ELECTRON_MIRROR", mirror), ("ELECTRON_BUILDER_BINARIES_MIRROR", builder_mirror)):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    print(f"[探活] 上游 fork      : {UPSTREAM}")
    print(f"[探活] 本地 .env.windows: {'存在' if ENV_FILE.is_file() else '缺失'}")
    print(f"[探活] 企业层 tgz     : {len(tarballs)} 个")
    print(f"[注入] ELECTRON_MIRROR: {mirror or '（未注入，走上游默认 github）'}")
    print(f"[注入] ELECTRON_BUILDER_BINARIES_MIRROR: {builder_mirror or '（未注入，走上游默认 github）'}")
    print(f"[执行] cd {UPSTREAM}")
    print(f"[执行] {' '.join(pnpm())} run {PACKAGE_SCRIPT}")
    for problem in problems:
        print(f"[FAIL] {problem}")
    if problems:
        return 1
    if args.dry_run:
        print("[OK] --dry-run：未执行打包")
        return 0

    completed = subprocess.run([*pnpm(), "run", PACKAGE_SCRIPT], cwd=str(UPSTREAM))
    print("-" * 60)
    print(f"打包命令退出码 = {completed.returncode}（0 为成功；产物见 "
          f"apps/desktop/.desktop-build/targets/win-x64/unsigned-artifacts/）")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
