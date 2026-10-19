#!/usr/bin/env python
"""差异集 11 门禁：安装态 CLI 壳品牌残留（launcher 占位符 + 产品名单一来源）。

背景：安装态 `resources/runtime/cli/bin/dsh.cmd` 由 `apps/desktop/cli/dsh.cmd` 拷贝而来，
资产里写死了上游可执行名 `DeepSeek Harness.exe`，而本发行版的可执行文件是
`WorkNexus-DSH.exe` → 直接运行该 CLI 壳报 `'...DeepSeek Harness.exe' is not recognized`（exit 9009）。
该文件在 `app.asar` 之外，因此 T-107 的 `app.asar` 品牌统计覆盖不到它。

断言：
  P1  差异集 11 补丁存在，权威枚举 = 4 个上游文件
  P2  两个 launcher 资产不含上游产品名、不含已解析的产品名，只含占位符
  P3  `prepare-cli.ts` 从产品名单一来源替换占位符，且占位符缺失即报错
  P4  行为：真实执行 `prepareDesktopCli`，Windows 产物指向 `WorkNexus-DSH.exe`、macOS 产物指向 `WorkNexus-DSH`
  P5  上游夹具已同步：`cli-launcher.spec.ts` 不再含上游产品名，改为引用产品名单一来源
  P6  回归：上游 `cli-launcher` 用例全绿
  P3  扩项：CLI 自身 `--help` 描述文案已是本产品名，其上游期望快照同步
P7  上游差异集条目数 = 120

用法：python scripts/verify_diffset11_cli_shell.py [--no-suite]
退出码：全部通过为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
PATCH = REPO / "patches" / "diffset-11-cli-shell.patch"
TOKEN = "__DSH_DESKTOP_PRODUCT_NAME__"
PRODUCT_NAME = "WorkNexus-DSH"
UPSTREAM_NAME = "DeepSeek Harness"
EXPECTED_FILES = sorted([
    "apps/cli/src/args.ts",
    "apps/cli/tests/expected/launcher-help.txt",
    "apps/desktop/cli/dsh",
    "apps/desktop/cli/dsh.cmd",
    "apps/desktop/scripts/prepare-cli.ts",
    "apps/desktop/tests/cli-launcher.spec.ts",
])
EXPECTED_DIFFSET_PATHS = 120

PROBE_SOURCE = """\
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { prepareDesktopCli } from '../apps/desktop/scripts/prepare-cli.ts'

const root = mkdtempSync(join(tmpdir(), 'd11-cli-'))
const windows = join(root, 'win')
const macos = join(root, 'macos')
prepareDesktopCli(windows, 'win32')
prepareDesktopCli(macos, 'darwin')
console.log('RESULT ' + JSON.stringify({
  cmd: readFileSync(join(windows, 'bin', 'dsh.cmd'), 'utf8'),
  sh: readFileSync(join(macos, 'bin', 'dsh'), 'utf8'),
}))
"""

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


def run_prepare_probe() -> dict[str, str]:
    tsx = UPSTREAM / "node_modules" / ".bin" / ("tsx.CMD" if sys.platform == "win32" else "tsx")
    if not tsx.exists():
        record(False, f"P4 探针前置缺失：找不到 {tsx}")
        return {}
    probe_dir = Path(tempfile.mkdtemp(prefix=".d11-probe-", dir=str(UPSTREAM)))
    try:
        (probe_dir / "probe.mts").write_text(PROBE_SOURCE, encoding="utf-8")
        proc = subprocess.run([str(tsx), str(probe_dir / "probe.mts")], cwd=str(UPSTREAM),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            record(False, f"P4 探针执行失败：exit={proc.returncode} {(proc.stderr or proc.stdout).strip()[-300:]}")
            return {}
        for line in proc.stdout.splitlines():
            if line.startswith("RESULT "):
                return json.loads(line[len("RESULT "):])
        record(False, "P4 探针无输出")
        return {}
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-suite", action="store_true", help="跳过上游 cli-launcher 用例回归")
    args = parser.parse_args()

    print("=" * 60)
    print("差异集 11 门禁：安装态 CLI 壳品牌残留")
    print("=" * 60)

    # ── P1 补丁枚举 ──
    text = read(PATCH)
    files = sorted({m.group(1) for m in re.finditer(r"^diff --git a/(.+?) b/", text, re.MULTILINE)})
    record(bool(text) and files == EXPECTED_FILES,
           f"P1 差异集 11 权威枚举 = {files}")

    # ── P2 launcher 资产 ──
    cmd_asset = read(UPSTREAM / "apps/desktop/cli/dsh.cmd")
    sh_asset = read(UPSTREAM / "apps/desktop/cli/dsh")
    record(TOKEN in cmd_asset and f"{TOKEN}.exe" in cmd_asset and UPSTREAM_NAME not in cmd_asset
           and PRODUCT_NAME not in cmd_asset,
           "P2 dsh.cmd 只含占位符（无上游产品名、未写死本发行版名）")
    record(TOKEN in sh_asset and f"MacOS/{TOKEN}" in sh_asset and UPSTREAM_NAME not in sh_asset
           and PRODUCT_NAME not in sh_asset,
           "P2 macOS dsh 只含占位符（同上）")

    # ── P3 打包脚本 ──
    prepare = read(UPSTREAM / "apps/desktop/scripts/prepare-cli.ts")
    record("desktop-product-name.mjs" in prepare and "DESKTOP_PRODUCT_NAME" in prepare,
           "P3 prepare-cli.ts 引用产品名单一来源 desktop-product-name.mjs")
    record("replaceAll(PRODUCT_NAME_TOKEN, DESKTOP_PRODUCT_NAME)" in prepare,
           "P3 prepare-cli.ts 用产品名替换占位符")
    record("does not carry" in prepare and "throw new Error" in prepare,
           "P3 占位符缺失时 fail loud（不静默拷贝上游名）")

    # ── P3b CLI 自身文案扩项 ──
    cli_args = read(UPSTREAM / "apps/cli/src/args.ts")
    expected_help = read(UPSTREAM / "apps/cli/tests/expected/launcher-help.txt")
    record(f"boot a {PRODUCT_NAME} profile" in cli_args and UPSTREAM_NAME not in cli_args,
           "P3b CLI `--help` 描述文案为本产品名（`apps/cli/src/args.ts`）")
    record(f"boot a {PRODUCT_NAME} profile" in expected_help and UPSTREAM_NAME not in expected_help,
           "P3b 其上游期望快照同步（`launcher-help.txt`）")

    # ── P4 行为探针 ──
    probe = run_prepare_probe()
    if probe:
        cmd = probe.get("cmd", "")
        sh = probe.get("sh", "")
        record(f'"{PRODUCT_NAME}.exe"' in cmd.replace("\\", "/") or f"{PRODUCT_NAME}.exe" in cmd,
               "P4 安装态 dsh.cmd 指向 WorkNexus-DSH.exe")
        record(UPSTREAM_NAME not in cmd and UPSTREAM_NAME not in sh,
               "P4 两个安装态 launcher 都不含上游产品名")
        record(f"MacOS/{PRODUCT_NAME}" in sh, "P4 安装态 macOS launcher 指向 WorkNexus-DSH")

    # ── P5 上游夹具同步 ──
    fixture = read(UPSTREAM / "apps/desktop/tests/cli-launcher.spec.ts")
    record("desktop-product-name.mjs" in fixture and "DESKTOP_PRODUCT_NAME" in fixture
           and UPSTREAM_NAME not in fixture,
           "P5 cli-launcher 夹具改为引用产品名单一来源（不含上游名）")

    # ── P6 上游用例回归 ──
    if args.no_suite:
        print("[跳过] P6 上游 cli-launcher 用例（--no-suite）")
    else:
        vitest = UPSTREAM / "node_modules" / ".bin" / ("vitest.CMD" if sys.platform == "win32" else "vitest")
        if not vitest.exists():
            record(False, f"P6 找不到上游 vitest：{vitest}")
        else:
            proc = subprocess.run([str(vitest), "run", "--project", "thread-safe",
                                   "apps/desktop/tests/cli-launcher.spec.ts"],
                                  cwd=str(UPSTREAM), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            record(proc.returncode == 0 and "failed" not in proc.stdout.lower(),
                   "P6 上游 cli-launcher 用例全绿（0 failed）")

    # ── P7 差异集条目数 ──
    paths = changed_paths()
    record(len(paths) == EXPECTED_DIFFSET_PATHS,
           f"P7 上游差异集条目数 = {len(paths)}（01~12 的 105 + 13 新增 13 + 14 新增 1）")
    record(all(path in paths for path in EXPECTED_FILES),
           "P7 差异集 11 的 4 个文件都在改动集内")

    failures = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failures)} [OK] / {len(failures)} [FAIL]")
    for detail in failures:
        print(f"  - {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
