#!/usr/bin/env python
"""T-106 门禁：发行物打包集成（企业层与合规文件随包）。

断言：
  P1  差异集 02 补丁存在且枚举 = 3 个上游文件
  P2  三处 seam 在工作树内就位（企业 bundle 清单 / 包集闭包根 + tgz 目录 / 合规文件 extraResources）
  P3  企业 tgz 目录存在且 tarball 数 = 13（`python scripts/pack_enterprise.py` 已运行）
  P4  运行时描述符 `desktop-runtime.json` 的 sharedPackages 含 13 个 `@worknexus/*`
  P5  运行时完整性清单内含 `node_modules/@worknexus/*` 文件
  P6  未签名安装包产物存在（win-x64）
  P7  安装目录 `resources/` 含 `THIRD_PARTY_NOTICES.md` 与 `WORKNEXUS-RELEASE-NOTES.md`
  P8  `app.asar` 内含企业 bundle 名
  P9  负向：上游共享 profile 模板 `packages/boot/app-boot/src/profile.ts` 未被改动

前置：先运行 `python scripts/pack_enterprise.py`，并在上游树执行一次
      `pnpm run package:desktop:win:x64:unsigned`（约 9 分钟）。
用法：python scripts/verify_t106_packaging.py
退出码：全部通过为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
TARGET = UPSTREAM / "apps" / "desktop" / ".desktop-build" / "targets" / "win-x64"
PATCH = REPO / "patches" / "diffset-02-package-integration.patch"
PACKED = REPO / ".worknexus-packed"
EXPECTED_FILES = [
    "apps/desktop/scripts/prepare-package-set.ts",
    "apps/desktop/src/project-manager.ts",
    "apps/desktop/scripts/electron-builder-config.mjs",
]
EXPECTED_ENTERPRISE_PACKAGES = 13

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(UPSTREAM), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.stdout


def changed_paths() -> list[str]:
    tracked = [line.strip() for line in git("diff", "--name-only", "HEAD").splitlines() if line.strip()]
    untracked = [line.strip() for line in git("ls-files", "--others", "--exclude-standard").splitlines() if line.strip()]
    return sorted(set(tracked + untracked))


def finish() -> int:
    failures = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failures)} [OK] / {len(failures)} [FAIL]")
    return 1 if failures else 0


def main() -> int:
    # ── P1 差异集 02 补丁 ──
    patch_text = read(PATCH)
    patch_files = sorted(set(re.findall(r"^diff --git a/(\S+)", patch_text, flags=re.MULTILINE)))
    record(bool(patch_text) and patch_files == sorted(EXPECTED_FILES),
           f"P1 差异集 02 补丁存在且枚举 = {patch_files}（{len(patch_text)} 字节）")

    # ── P2 三处 seam ──
    pm = read(UPSTREAM / EXPECTED_FILES[1])
    record("WORKNEXUS_PROFILE_BUNDLES" in pm and "DESKTOP_PROFILE_BUNDLES" in pm
           and "initProfile(projectDir, DESKTOP_PROFILE_BUNDLES)" in pm
           and "sanitizeProfile('dsh', this.paths.profile, DESKTOP_PROFILE_BUNDLES)" in pm,
           "P2a 桌面 profile 预置企业 bundle 清单（含原生恢复同一清单）")
    pps = read(UPSTREAM / EXPECTED_FILES[0])
    record("WORKNEXUS_ROOT_PACKAGES" in pps and "WORKNEXUS_PACKED_DIR" in pps
           and "extraRoots" in pps,
           "P2b 包集闭包纳入企业根与企业 tgz 目录")
    ebc = read(UPSTREAM / EXPECTED_FILES[2])
    record("THIRD_PARTY_NOTICES.md" in ebc and "WORKNEXUS-RELEASE-NOTES.md" in ebc,
           "P2c 合规文件随包落点（electron-builder extraResources）")

    # ── P3 企业 tgz ──
    tarballs = sorted(p.name for p in PACKED.glob("*.tgz")) if PACKED.is_dir() else []
    record(len(tarballs) == EXPECTED_ENTERPRISE_PACKAGES,
           f"P3 企业 tarball 数 = {len(tarballs)}（期望 {EXPECTED_ENTERPRISE_PACKAGES}）")

    # ── P4/P5 运行时描述符 ──
    descriptor_path = TARGET / "dsh" / "desktop-runtime.json"
    descriptor = json.loads(read(descriptor_path)) if descriptor_path.exists() else {}
    shared = descriptor.get("sharedPackages", [])
    enterprise = [entry for entry in shared if str(entry.get("name", "")).startswith("@worknexus/")]
    record(len(enterprise) == EXPECTED_ENTERPRISE_PACKAGES,
           f"P4 运行时 sharedPackages 含企业包 = {len(enterprise)}（总 {len(shared)}）")
    enterprise_files = [f for f in descriptor.get("files", [])
                        if str(f.get("path", "")).startswith("node_modules/@worknexus/")]
    record(len(enterprise_files) > 0,
           f"P5 运行时完整性清单含企业文件 = {len(enterprise_files)}（总文件 {len(descriptor.get('files', []))}）")

    # ── P6 安装包 ──
    artifacts = sorted((TARGET / "unsigned-artifacts").glob("*.exe")) if (TARGET / "unsigned-artifacts").is_dir() else []
    record(bool(artifacts), f"P6 安装包产物 = {[a.name for a in artifacts]}")
    resources = TARGET / "unsigned-artifacts" / "win-unpacked" / "resources"
    for name in ("THIRD_PARTY_NOTICES.md", "WORKNEXUS-RELEASE-NOTES.md"):
        record((resources / name).exists(), f"P7 安装目录含 {name}")

    # ── P8 app.asar 内企业 bundle 名 ──
    asar = resources / "app.asar"
    blob = asar.read_bytes() if asar.exists() else b""
    hits = blob.count(b"@worknexus/ent-core")
    record(hits > 0, f"P8 app.asar 内企业 bundle 名命中 = {hits}")

    # ── P9 负向：共享 profile 模板未被改动 ──
    shared_template = "packages/boot/app-boot/src/profile.ts"
    record(shared_template not in changed_paths(),
           f"P9 上游共享 profile 模板未被改动（差异集 {len(changed_paths())} 条）")

    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
