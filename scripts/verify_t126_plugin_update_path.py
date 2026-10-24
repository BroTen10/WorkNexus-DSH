#!/usr/bin/env python
"""T-126 门禁：已安装插件的市场更新路径（DSH 0.2.1 already-installed 语义）。

背景（2026-10-18 真机）：插件市场对已安装插件点「更新」时报
`{"code":"already-installed"}`，随后回滚校验又因 `pnpm-lock.yaml` 与
`node_modules` 版本不一致而拒绝，页面显示「更新失败……无法证明精确来源」。

两个根因：
  1. `dshmarket@1.66.9` 把市场的 `add <spec>` 直接映射成官方
     `installBundle(spec)`；DSH 0.2.1 的 manager 对已安装包在跑 pnpm 之前
     就以 `already-installed` 拒绝，更新必须 `removeBundle` → install。
     `dshmarket@1.66.37` 已实现该回退（上游 #896/#897）；当前跟版的
     `1.66.45` 继续保持，并修正了 release-age 等待期假回滚。
  2. 启动补齐把市场装上的新版本强行改回随包版本，且不修 `pnpm-lock.yaml`。
     现在只做「向前同步」：低于随包版本才改，等于/高于一律保留。

本门禁做四件事：
  A. 锁文件与运行时树的 dshmarket / undici 版本一致且已跟到修复版；
  B. 静态确认运行时 `official-desktop.js` 含 already-installed 的 remove 回退，
     以及 1.66.40/41 的「宿主在 pnpm 前失败则不回滚」与机器可读拒绝码；
  C. 行为探针：假 manager 第一次 install 返回 already-installed，断言市场
     依次调用 install → remove → install 并以 exit=0 结束；
  D. 静态确认启动补齐只向前同步（存在 compareExactVersions，且不再按
     `existing !== spec` 回退）。

退出码：全部通过 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
DESKTOP = UPSTREAM / "apps" / "desktop"
RUNTIME = DESKTOP / ".desktop-build" / "targets" / "win-x64" / "dsh" / "node_modules"
LOCK = REPO / "configs" / "vendor" / "third-party-bundles.lock.json"
BACKFILL = DESKTOP / "src" / "profile-bundle-backfill.ts"

EXPECTED = {"dshmarket": "1.66.45", "undici": "7.29.1"}
RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def package_version(directory: Path) -> str | None:
    try:
        return json.loads((directory / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def lock_versions() -> dict[str, str]:
    try:
        packages = json.loads(LOCK.read_text(encoding="utf-8"))["packages"]
    except (OSError, json.JSONDecodeError, KeyError):
        return {}
    return {item["name"]: item["version"] for item in packages if item["name"] in EXPECTED}


def run_reinstall_probe() -> dict[str, object]:
    """用运行时真实的 dshmarket lib + 假 manager 跑一次更新。"""
    entry = RUNTIME / "dshmarket" / "lib" / "official-desktop.js"
    if not entry.is_file():
        return {"error": f"missing {entry}"}
    script = """\
import { createOfficialDesktopRuntime } from __ENTRY__
const calls = []
let installs = 0
const manager = {
  installBundle: async (spec) => {
    calls.push(`install:${spec}`)
    installs += 1
    return installs === 1
      ? { application: 'failed', error: { code: 'already-installed' } }
      : { application: 'applied' }
  },
  removeBundle: async (name) => {
    calls.push(`remove:${name}`)
    return { application: 'applied' }
  },
  cancelInstall: async () => {},
}
const runtime = createOfficialDesktopRuntime(() => manager, 'desktop')
const result = await runtime.runPlugin('desktop', ['add', 'dsh-claude-style@0.18.1'])
console.log(JSON.stringify({ exitCode: result.exitCode, calls }))
""".replace("__ENTRY__", json.dumps(entry.as_uri()))
    directory = Path(tempfile.mkdtemp(prefix="t126-probe-"))
    probe = directory / "probe.mjs"
    try:
        probe.write_text(script, encoding="utf-8")
        proc = subprocess.run(["node", str(probe)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)
        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout).strip()[-300:]}
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        return {"error": str(error)}
    finally:
        for child in directory.glob("*"):
            child.unlink(missing_ok=True)
        directory.rmdir()


def main() -> int:
    print("=" * 60)
    print("T-126 门禁：已安装插件的市场更新路径")
    print("=" * 60)

    # A. 版本一致性
    locked = lock_versions()
    record(locked == EXPECTED,
           f"A1 锁文件 dshmarket/undici = {locked}（期望 {EXPECTED}）")
    runtime = {name: package_version(RUNTIME / name) for name in EXPECTED}
    record(runtime == EXPECTED,
           f"A2 运行时树 dshmarket/undici = {runtime}（期望 {EXPECTED}）")

    # B. 静态回退
    entry_source = read(RUNTIME / "dshmarket" / "lib" / "official-desktop.js")
    record("'already-installed'" in entry_source and "removeBundle" in entry_source
           and "installOrReinstall" in entry_source,
           "B1 运行时市场的官方桌面桥含 already-installed → removeBundle → install 回退")
    record("function prePnpmHostFailure" in entry_source and "wroteNothing" in entry_source
           and "refusalCode" in entry_source,
           "B2 宿主在 pnpm 前拒绝时标记 wroteNothing，并保留 refusalCode（1.66.40/41）")
    profile_source = read(RUNTIME / "dshmarket" / "lib" / "profile.js")
    record("function hasLoadableEntry" in profile_source and "hostDirectory" in profile_source
           and "findDshInstallDir" in profile_source,
           "B3 carrier 判定读取宿主安装树，避免把仅挂载内置包的插件误删（1.66.45）")

    # C. 行为探针
    probe = run_reinstall_probe()
    calls = probe.get("calls")
    record(probe.get("exitCode") == 0
           and calls == ["install:dsh-claude-style@0.18.1",
                         "remove:dsh-claude-style",
                         "install:dsh-claude-style@0.18.1"],
           f"C1 更新探针：install → remove → install，exit=0（实测 {probe}）")

    # D. 启动补齐只向前
    backfill = read(BACKFILL)
    record("function compareExactVersions" in backfill
           and re.search(r"const order = existing === undefined \? -1 : compareExactVersions", backfill) is not None
           and "existing !== spec" not in backfill,
           "D1 启动补齐只向前同步：高于随包版本的精确版本保留，不再按 existing !== spec 回退")

    failures = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failures)} [OK] / {len(failures)} [FAIL]")
    for detail in failures:
        print(f"  - {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
