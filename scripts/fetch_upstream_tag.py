#!/usr/bin/env python
"""按 tag 获取上游基线（T-020 的可复现获取与校验方式）。

为什么不用 `git clone`：本机到 github.com 的 git 传输会被重置
（`Recv failure: Connection was reset`），而 HTTPS 下载通道可用。
因此固定为「codeload tar.gz + 本地解包 + 计数与哈希校验」。

Windows 注意：上游树含超长路径（> 260 字符），必须用 `\\\\?\\` 前缀解包，
否则 tar/bsdtar 会静默丢掉约 12% 的文件。

用法：
  python scripts/fetch_upstream_tag.py --tag dsh-v0.2.0-rc.2
  python scripts/fetch_upstream_tag.py --tag dsh-v0.2.0-rc.2 --archive <本地 tar.gz>
输出：仓库内 repos/deepseek-harness（repos/ 已在 .gitignore）
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
REPOS = REPO / "repos"
TARGET = REPOS / "deepseek-harness"
STAGING = REPOS / "_staging"
LONG = "\\\\?\\"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(tag: str, dest: Path, timeout: int = 1800) -> None:
    url = f"https://codeload.github.com/deepseek-ai/deepseek-harness/tar.gz/refs/tags/{tag}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[..] 下载 {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "worknexus-dsh-baseline"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    print(f"[OK] 下载完成 {dest.name} = {dest.stat().st_size} 字节，用时 {time.time() - t0:.1f}s")


def extract(archive: Path, staging: Path) -> int:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    prefixed = LONG + str(staging)
    n = 0
    with tarfile.open(archive) as tf:
        for m in tf:
            name = m.name.split("/", 1)
            if len(name) < 2:
                continue
            rel = name[1]
            target = os.path.join(prefixed, rel.replace("/", os.sep))
            if m.isdir():
                os.makedirs(target, exist_ok=True)
            elif m.isfile():
                os.makedirs(os.path.dirname(target), exist_ok=True)
                src = tf.extractfile(m)
                if src is None:
                    continue
                with open(target, "wb") as out:
                    while True:
                        b = src.read(1 << 20)
                        if not b:
                            break
                        out.write(b)
                n += 1
    return n


def count_files(root: Path) -> int:
    total = 0
    for _, dirs, files in os.walk(LONG + str(root)):
        total += len(files)
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--archive", help="本地已下载的 tar.gz（跳过下载）")
    ap.add_argument("--expect-files", type=int, default=0, help="期望文件数（0 表示不校验）")
    args = ap.parse_args()

    archive = Path(args.archive) if args.archive else Path(os.environ["TEMP"]) / f"{args.tag}.tar.gz"
    if not archive.exists():
        download(args.tag, archive)
    digest = sha256_of(archive)
    print(f"[OK] tar.gz sha256 = {digest}")

    n = extract(archive, STAGING)
    on_disk = count_files(STAGING)
    print(f"[OK] 解包文件数 = {n}（磁盘计数 {on_disk}）")
    if args.expect_files and on_disk < args.expect_files:
        print(f"[FAIL] 期望 ≥ {args.expect_files} 个文件，实际 {on_disk}")
        return 1

    if TARGET.exists():
        print(f"[..] 移除旧基线 {TARGET}")
        shutil.rmtree(LONG + str(TARGET))
    shutil.move(LONG + str(STAGING), LONG + str(TARGET))
    print(f"[OK] 上游基线就位: {TARGET}")
    print(f"[i]  校验用：tag={args.tag} 文件数={on_disk} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
