#!/usr/bin/env python
"""差异集 09 门禁：安装器卸载残留与 Harness 主目录卸载选项。

断言（全部使用上游 `test:installer` 编译出的**隔离身份**测试安装器，不触碰真实安装）：
  P1 上游 fork 与差异集 09 补丁存在（3 个文件）
  P2 上游安装器可编译（`node scripts/test-windows-installer.mjs --compile-only`）
  P3 静默安装不留下 %TEMP%\\ns*.tmp（安装前后计数）
  P4 默认静默卸载：不留 ns*.tmp，且 DSH_HOME 指向的 Harness 主目录保留
  P5 `/PURGE_HOME` 静默卸载：删除 Harness 主目录，且不留 ns*.tmp
  P6 `/PURGE_HOME /KEEP_HOME` 同传：`/KEEP_HOME` 优先，主目录保留
  P7 全过程真实 `~/.dsh` 未被触碰（仅在 DSH_HOME 指向测试目录时成立）

命名说明：本差异集没有任务卡，故不套用 `verify_t<编号>_<域>.py`；裁决见
`docs/差异集清单.md` 的 DS-6。

用法：
  python scripts/verify_diffset09_installer_cleanup.py
  python scripts/verify_diffset09_installer_cleanup.py --keep-scratch   # 保留现场便于排查
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
DESKTOP = UPSTREAM / "apps" / "desktop"
PATCH = REPO / "patches" / "diffset-09-installer-cleanup.patch"
SCRATCH_ROOT = REPO / ".dsh-check" / "t109"
EXPECTED_PATCH_FILES = [
    "apps/desktop/installer/uninstall.nsh",
    "apps/desktop/scripts/installer-directories.nsh",
    "apps/desktop/scripts/installer.nsh",
]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def info(detail: str) -> None:
    print(f"[INFO] {detail}")


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for flag, _ in RESULTS if flag)
    bad = sum(1 for flag, _ in RESULTS if not flag)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


def temp_residue() -> set[str]:
    """%TEMP% 下 NSIS 插件目录的当前快照（只比较有无，不删别人的东西）。"""
    # 让上一阶段进程的 NSIS 收尾彻底跑完，否则会把别人的收尾算到自己头上。
    time.sleep(1.5)
    temp = Path(tempfile.gettempdir())
    return {item.name for item in temp.glob("ns*.tmp") if item.is_dir()}


def wait_no_installer(timeout: float = 20.0) -> bool:
    """等上一阶段的安装器/卸载器进程退出，避免并发收尾污染计数。"""
    script = ("$n = @(Get-Process | Where-Object { $_.Path -like '*installer-test*' "
              "-or $_.Path -like '*uninstall-copy*' }).Count; Write-Output $n")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run(["powershell", "-NoProfile", "-Command", script], REPO)
        if (result.stdout or "").strip().endswith("0"):
            return True
        time.sleep(0.5)
    return False


def run(args: list[str], cwd: Path, env: dict | None = None, timeout: int = 900):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=timeout)


def wait_gone(path: Path, seconds: float = 25.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not path.exists():
            return True
        time.sleep(0.1)
    return not path.exists()


def uninstall(scratch: Path, install_dir: Path, home: Path, switches: list[str]) -> tuple[int, str]:
    """复制并运行安装目录里的卸载器；DSH_HOME 指向测试主目录，绝不指向真实 ~/.dsh。"""
    candidates = list(install_dir.glob("Uninstall *.exe"))
    if not candidates:
        return -1, "安装目录里没有卸载器"
    copy = scratch / "uninstall-copy.exe"
    shutil.copy2(candidates[0], copy)
    env = dict(os.environ, DSH_HOME=str(home))
    result = run([str(copy), *switches, f"_?={install_dir}"], scratch, env=env, timeout=300)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-scratch", action="store_true")
    args = parser.parse_args()

    if os.name != "nt":
        record(False, "本门禁只在 Windows 上可执行（NSIS 安装器）")
        return finish()

    record(UPSTREAM.is_dir() and DESKTOP.is_dir(), f"上游 fork 存在: {UPSTREAM}")
    if PATCH.exists():
        names = sorted(set(re.findall(r"^diff --git a/(\S+)", PATCH.read_text(encoding="utf-8"),
                                      flags=re.MULTILINE)))
        record(names == EXPECTED_PATCH_FILES,
               f"P1 差异集 09 补丁枚举 = {len(names)} 文件（{PATCH.stat().st_size} 字节）")
    else:
        record(False, f"P1 差异集 09 补丁缺失: {PATCH}")
        return finish()

    if SCRATCH_ROOT.exists():
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    scratch = SCRATCH_ROOT
    install_dir = scratch / "Installed App"
    home = scratch / "Harness Home"
    real_home = Path(os.path.expanduser("~")) / ".dsh"
    real_before = sorted(p.relative_to(real_home).as_posix() for p in real_home.rglob("*")) \
        if real_home.exists() else []

    # ── P2 编译隔离测试安装器 ──
    compile_run = run(["node", "scripts/test-windows-installer.mjs", "--compile-only"], DESKTOP)
    match = re.search(r"Installer test artifacts: (.+)", compile_run.stdout or "")
    if compile_run.returncode != 0 or not match:
        record(False, f"P2 测试安装器编译失败（exit={compile_run.returncode}）")
        info((compile_run.stdout or "")[-500:] + (compile_run.stderr or "")[-500:])
        return finish()
    artifacts = Path(match.group(1).strip())
    installers = sorted(artifacts.glob("*/installer-test.exe"))
    record(bool(installers), f"P2 测试安装器编译成功 = {len(installers)} 个（{artifacts.name}）")
    if not installers:
        return finish()
    installer = installers[0]

    wait_no_installer()
    baseline = temp_residue()
    info(f"运行前 %TEMP%\\ns*.tmp = {len(baseline)} 个")

    def install() -> tuple[int, str]:
        result = run([str(installer), "/S", f"/D={install_dir}"], scratch, timeout=600)
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def prepare_home() -> None:
        home.mkdir(parents=True, exist_ok=True)
        (home / "sessions").mkdir(exist_ok=True)
        (home / "sessions" / "keep.txt").write_text("keep session", encoding="utf-8")
        (home / ".credentials.yaml").write_text("token: keep", encoding="utf-8")

    # ── P3 + P4 默认路径：装、卸各不留残留；主目录保留 ──
    code, output = install()
    installed = code == 0
    record(installed, f"P3 静默安装 exit={code}")
    if not installed:
        info(output[-400:])
        return finish()
    after_install = temp_residue()
    new_after_install = after_install - baseline
    record(not new_after_install, f"P3 安装未新增 ns*.tmp（新增 {sorted(new_after_install) or '无'}）")
    prepare_home()
    code, output = uninstall(scratch, install_dir, home, ["/S", "/currentuser"])
    removed = wait_gone(install_dir)
    record(code == 0 and removed, f"P4 默认静默卸载 exit={code}，安装目录已移除={removed}")
    after_default = temp_residue()
    new_after_default = after_default - after_install
    record(not new_after_default, f"P4 卸载未新增 ns*.tmp（新增 {sorted(new_after_default) or '无'}）")
    record((home / "sessions" / "keep.txt").exists(),
           "P4 默认卸载保留 Harness 主目录（含会话与凭据）")

    # ── P5 `/PURGE_HOME` 删主目录 ──
    code, _ = install()
    if code != 0:
        record(False, f"P5 重新安装失败 exit={code}")
        return finish()
    prepare_home()
    before_purge = temp_residue()
    code, output = uninstall(scratch, install_dir, home, ["/S", "/currentuser", "/PURGE_HOME"])
    removed = wait_gone(install_dir)
    record(code == 0 and removed, f"P5 /PURGE_HOME 卸载 exit={code}，安装目录已移除={removed}")
    record(not home.exists(), f"P5 /PURGE_HOME 删除 Harness 主目录（残留={home.exists()}）")
    after_purge = temp_residue()
    new_after_purge = after_purge - before_purge
    record(not new_after_purge, f"P5 卸载未新增 ns*.tmp（新增 {sorted(new_after_purge) or '无'}）")

    # ── P6 `/KEEP_HOME` 覆盖 `/PURGE_HOME` ──
    code, _ = install()
    if code != 0:
        record(False, f"P6 重新安装失败 exit={code}")
        return finish()
    prepare_home()
    code, output = uninstall(scratch, install_dir, home, ["/S", "/currentuser", "/PURGE_HOME", "/KEEP_HOME"])
    wait_gone(install_dir)
    record(code == 0 and (home / "sessions" / "keep.txt").exists(),
           f"P6 /KEEP_HOME 优先于 /PURGE_HOME，主目录保留（exit={code}）")

    # ── P7 真实 ~/.dsh 未被触碰 ──
    real_after = sorted(p.relative_to(real_home).as_posix() for p in real_home.rglob("*")) \
        if real_home.exists() else []
    record(real_before == real_after, f"P7 真实 ~/.dsh 未被触碰（{len(real_after)} 个条目）")

    if not args.keep_scratch:
        shutil.rmtree(scratch, ignore_errors=True)
    else:
        info(f"现场保留: {scratch}")
    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
