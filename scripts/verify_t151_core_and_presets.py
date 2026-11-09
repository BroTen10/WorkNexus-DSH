#!/usr/bin/env python
"""T-151 门禁：官方核心跟版与个人版随包范围。

断言：
  G1 锁定的桌面核心与官方 tag 一致；
  G2 上游 HEAD 是官方提交，而不是本地快照提交；
  G3 第三方 bundle 根只含 dshmarket，且版本为 1.73.14；
  G4 个人预置包集精确等于锁文件；
  G5 官方默认 bundle 文件相对锁定 tag 未被改动；
  G6 桌面 profile 初值直接使用官方 Web 模板。

用法：python scripts/verify_t151_core_and_presets.py
退出码：全部 [OK] 为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
DESKTOP_PACKAGE = UPSTREAM / "apps" / "desktop" / "package.json"
LOCK = REPO / "configs" / "vendor" / "third-party-bundles.lock.json"
PACKED = REPO / ".worknexus-packed"
PROJECT_MANAGER = UPSTREAM / "apps" / "desktop" / "src" / "project-manager.ts"
OFFICIAL_BUNDLE_FILES = (
    "packages/boot/app-boot/src/profile.ts",
    "packages/util/official-bundles/src/bundles.ts",
    "packages/util/official-bundles/src/catalog.generated.ts",
    "packages/util/official-bundles/src/plugin-manager.ts",
)
EXPECTED_TAG = "dsh-v0.2.2-rc.1"
EXPECTED_COMMIT = "66491b05e3f05ad35bcdd4f6cd7ed26041d9e3db"
EXPECTED_VERSION = "0.2.2-rc.1"
EXPECTED_ROOTS = {"dshmarket": "1.73.14"}
RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(UPSTREAM),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> int:
    desktop = json.loads(DESKTOP_PACKAGE.read_text(encoding="utf-8"))
    record(
        desktop.get("name") == "@deepseek-ai/dsh-desktop" and desktop.get("version") == EXPECTED_VERSION,
        f"G1 桌面核心 = {desktop.get('name')}@{desktop.get('version')}（期望 {EXPECTED_VERSION}）",
    )

    head = git("rev-parse", "HEAD")
    record(head.returncode == 0 and head.stdout.strip() == EXPECTED_COMMIT,
           f"G2 上游 HEAD = {head.stdout.strip()}（期望 {EXPECTED_TAG} @ {EXPECTED_COMMIT}）")

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    roots = {
        item["name"]: item["version"]
        for item in lock.get("packages", [])
        if item.get("role") == "bundle-root"
    }
    record(roots == EXPECTED_ROOTS,
           f"G3 第三方 bundle 根 = {roots}（期望 {EXPECTED_ROOTS}）")

    expected_files = {item["file"] for item in lock.get("packages", []) if item.get("file")}
    produced = {path.name for path in PACKED.glob("*.tgz")}
    record(produced == expected_files,
           f"G4 个人预置包集精确等于锁文件（actual={sorted(produced)} expected={sorted(expected_files)}）")

    defaults = git("diff", "--quiet", "HEAD", "--", *OFFICIAL_BUNDLE_FILES)
    record(defaults.returncode == 0,
           "G5 官方默认 bundle 定义相对锁定 tag 未改动")

    project_manager = PROJECT_MANAGER.read_text(encoding="utf-8")
    web_template = "const DESKTOP_PROFILE_BUNDLES: readonly string[] = WEB_PROFILE.bundles" in project_manager
    record(web_template, "G6 Desktop profile 初值直接使用官方 Web 模板")

    failed = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failed)} [OK] / {len(failed)} [FAIL]")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
