#!/usr/bin/env python
"""T-020 门禁：上游基线检出与可构建验证。

断言（默认档）：
  B1 上游基线目录存在
  B2 检出的是锁定 tag 的版本（apps/desktop/package.json version == 0.2.0-rc.2）
  B3 pnpm-lock.yaml 与 tag 压缩包内的原始字节一致（sha256 比对）
  B4 依赖已安装（node_modules 存在且规模达标）
  B5 root package.json 的 packageManager / engines 与文档登记一致
  B6 关键构建脚本存在（build:lib:host / typecheck / lint / package:desktop:win:x64）

可选档（--full）额外执行：
  B7 `pnpm run typecheck` 退出码 0
  B8 `pnpm run lint` 退出码 0

用法：
  python scripts/verify_t020_build.py
  python scripts/verify_t020_build.py --full
  python scripts/verify_t020_build.py --archive <tag tar.gz>   # 指定用于比对的原始压缩包
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
EXPECTED_VERSION = "0.2.0-rc.2"
# 基线迁移（2026-09-29，rc.1 → rc.2）：锁文件字节来源为上游 tag 提交
# 639ed015397290b3745d163aafe02ffee4aa3f84（`git ls-remote` 独立核对）。
# 证据链：tag → 提交哈希（远端核对）→ HEAD == 该提交 → 工作区相对 HEAD 干净；
# 上游 .gitattributes 强制 `* text=auto eol=lf`，故工作区字节 == 仓库 blob 字节。
EXPECTED_LOCK_SHA256 = "80fe05eae33582ae26839afd05f1965f9b0e4be11034ddf9797af6085d5ba9b1"
EXPECTED_PACKAGE_MANAGER = "pnpm@11.7.0"
MIN_PNPM_PACKAGE_DIRS = 1_000

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lock_sha_in_archive(archive: Path) -> str | None:
    if not archive.exists():
        return None
    with tarfile.open(archive) as tf:
        for m in tf.getmembers():
            if m.name.endswith("/pnpm-lock.yaml"):
                f = tf.extractfile(m)
                if f is None:
                    return None
                return hashlib.sha256(f.read()).hexdigest()
    return None


def count_pnpm_packages(upstream: Path) -> int:
    """快速结构检查：数 node_modules/.pnpm 下的包目录。

    不用递归文件计数——上游 node_modules 有 20 万+ 文件，os.walk 会拖到分钟级甚至卡死。
    """
    pnpm_dir = upstream / "node_modules" / ".pnpm"
    if not pnpm_dir.is_dir():
        return 0
    try:
        return sum(1 for entry in os.scandir(pnpm_dir) if entry.is_dir(follow_symlinks=False))
    except OSError:
        return 0


def run(cmd: list[str], cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["ELECTRON_SKIP_BINARY_DOWNLOAD"] = "1"
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env, timeout=timeout, shell=False,
    )


def pnpm_argv(upstream: Path) -> list[str]:
    """用仓库自带的 pnpm 11.7.0（README 推荐形式），避免依赖 PATH 上的 corepack。"""
    local = upstream / "node_modules" / "pnpm" / "bin" / "pnpm.mjs"
    if local.exists():
        return ["node", str(local)]
    return ["corepack", "pnpm"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="额外执行 typecheck 与 lint")
    ap.add_argument("--archive", default=str(Path(os.environ.get("TEMP", ".")) / "dsh-0.2.0-rc.2.tar.gz"))
    args = ap.parse_args()

    record(UPSTREAM.is_dir(), f"上游基线目录存在: {UPSTREAM}")
    if not UPSTREAM.is_dir():
        return finish()

    pkg_path = UPSTREAM / "apps" / "desktop" / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8")) if pkg_path.exists() else {}
    record(
        pkg.get("version") == EXPECTED_VERSION and pkg.get("name") == "@deepseek-ai/dsh-desktop",
        f"桌面端包为 {pkg.get('name')}@{pkg.get('version')}（期望 @deepseek-ai/dsh-desktop@{EXPECTED_VERSION}）",
    )

    lock = UPSTREAM / "pnpm-lock.yaml"
    on_disk = sha256_file(lock) if lock.exists() else ""
    record(on_disk == EXPECTED_LOCK_SHA256, f"pnpm-lock.yaml sha256 = {on_disk}")
    arch = lock_sha_in_archive(Path(args.archive))
    if arch is None:
        record(True, f"未提供 tag 压缩包（{args.archive}），跳过与原始字节的比对")
    else:
        record(arch == on_disk, "pnpm-lock.yaml 与 tag 压缩包内原始字节一致（安装未改动锁文件）")

    pnpm_pkgs = count_pnpm_packages(UPSTREAM)
    record(
        pnpm_pkgs >= MIN_PNPM_PACKAGE_DIRS,
        f"依赖已安装: node_modules/.pnpm 包目录数 = {pnpm_pkgs}（阈值 {MIN_PNPM_PACKAGE_DIRS}）",
    )

    root_pkg = json.loads((UPSTREAM / "package.json").read_text(encoding="utf-8"))
    record(
        root_pkg.get("packageManager") == EXPECTED_PACKAGE_MANAGER,
        f"packageManager = {root_pkg.get('packageManager')}（期望 {EXPECTED_PACKAGE_MANAGER}）",
    )
    record(
        root_pkg.get("engines", {}).get("node") == "^22.19.0 || >=24.0.0",
        f"engines.node = {root_pkg.get('engines', {}).get('node')}（本机 node 满足性由 V-7 单独登记）",
    )

    scripts = root_pkg.get("scripts", {})
    need = ["build:lib:host", "typecheck", "lint", "package:desktop:win:x64"]
    record(all(k in scripts for k in need), f"关键脚本齐备: {', '.join(need)}")

    if args.full:
        base = pnpm_argv(UPSTREAM)
        for name in ("typecheck", "lint"):
            r = run([*base, "run", name], UPSTREAM)
            tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
            record(r.returncode == 0, f"`pnpm run {name}` 退出码 {r.returncode}（末行: {tail[0][:120]}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for o, _ in RESULTS if o)
    bad = sum(1 for o, _ in RESULTS if not o)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
