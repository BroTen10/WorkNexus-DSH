#!/usr/bin/env python
"""T-108 门禁：客户端壳回归网（上游 `apps/desktop/tests` 一键运行且为绿）。

断言：
  P1  探活：上游 fork 存在、依赖已装（`node_modules` + vitest）
  P2  差异集 07 补丁存在，且文件枚举 = 23（apps/desktop/tests 的期望值与内联断言就地更新）
  P3  上游桌面壳套件全绿（`pnpm exec vitest run --project thread-safe apps/desktop/tests`，0 failed）
  P4  测试纪律未被削弱：无删除的测试文件、无新增 skip/todo、用例声明未增删
      （与 `verify_t028_release.py` 的 R6 并列，互不替代）
  P5  品牌期望留在原地：`apps/desktop/tests/**` 的品牌串只允许出现在**登记的自洽夹具**里，
      其余一律为 0（防止「就地更新」被悄悄换成 overlay 或漏改）

前置：无（本门禁只读上游树与补丁；不构建、不打包）。
用法：python scripts/verify_t108_client_regression.py [--no-suite]
退出码：全部 [OK] 为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
DESKTOP_TESTS = UPSTREAM / "apps" / "desktop" / "tests"
PATCH_07 = REPO / "patches" / "diffset-07-desktop-test-expectations.patch"

# 差异集 07 的权威枚举（23 条）：7 个 spec 的内联断言 + 16 个期望文件
EXPECTED_07 = sorted([
    "apps/desktop/tests/background-notice.spec.ts",
    "apps/desktop/tests/installer-packaging.spec.ts",
    "apps/desktop/tests/macos-signature.spec.ts",
    "apps/desktop/tests/main-startup.spec.ts",
    "apps/desktop/tests/quit-confirmation.spec.ts",
    "apps/desktop/tests/tray.spec.ts",
    "apps/desktop/tests/windows-update-publisher.spec.ts",
    "apps/desktop/tests/expected/application-menu-en-US.json",
    "apps/desktop/tests/expected/application-menu-zh-CN.json",
    "apps/desktop/tests/expected/fatal-address-in-use-en.txt",
    "apps/desktop/tests/expected/fatal-address-in-use-zh-CN.txt",
    "apps/desktop/tests/expected/fatal-dialog-en.txt",
    "apps/desktop/tests/expected/fatal-dialog-with-report-en.txt",
    "apps/desktop/tests/expected/fatal-dialog-with-report-zh-CN.txt",
    "apps/desktop/tests/expected/fatal-dialog-zh-CN.txt",
    "apps/desktop/tests/expected/welcome/en-api-key.expected.txt",
    "apps/desktop/tests/expected/welcome/en-timeout.expected.txt",
    "apps/desktop/tests/expected/welcome/en-waiting.expected.txt",
    "apps/desktop/tests/expected/welcome/en.expected.txt",
    "apps/desktop/tests/expected/welcome/zh-CN-api-key.expected.txt",
    "apps/desktop/tests/expected/welcome/zh-CN-timeout.expected.txt",
    "apps/desktop/tests/expected/welcome/zh-CN-waiting.expected.txt",
    "apps/desktop/tests/expected/welcome/zh-CN.expected.txt",
])

# P5：仍含上游产品名、但属**自洽夹具**（测试自己构造输入与期望，不依赖我方产品名）的文件。
# 每一条都在交付说明 §4 里登记了「为什么不改」。
FIXTURE_ALLOWLIST = {
    "apps/desktop/tests/cli-launcher.spec.ts": "安装目录/可执行名由测试自建夹具提供",
    "apps/desktop/tests/command-management.spec.ts": "dsh 命令路径由测试自建夹具提供",
    "apps/desktop/tests/expected/command-management-win32-en-US.json": "同上夹具的回显",
    "apps/desktop/tests/expected/command-management-win32-zh-CN.json": "同上夹具的回显",
    "apps/desktop/tests/crash-report.spec.ts": "崩溃报告输入夹具自带 app.name，断言即回显该输入",
    "apps/desktop/tests/fatal-recovery.spec.ts": "诊断报告路径常量（REPORT_PATH）是夹具输入",
    "apps/desktop/tests/expected/fatal-dialog-with-report-en.txt": "同上夹具路径的回显",
    "apps/desktop/tests/expected/fatal-dialog-with-report-zh-CN.txt": "同上夹具路径的回显",
    "apps/desktop/tests/macos-app-update-config.spec.ts": "macOS .app 目录名夹具",
    "apps/desktop/tests/macos-notarized-application.spec.ts": "macOS .app 目录名夹具",
    "apps/desktop/tests/package-macos.spec.ts": "macOS .app 目录名夹具",
    "apps/desktop/tests/windows-sign.spec.ts": "签名目标路径夹具",
}

BRAND = "DeepSeek Harness"
SUITE_GLOB = "apps/desktop/tests"

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


def run(args: list[str], cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def git(*args: str) -> str:
    return run(["git", *args], UPSTREAM).stdout


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def pnpm() -> list[str]:
    for candidate in ("pnpm.cmd", "pnpm"):
        found = shutil.which(candidate)
        if found:
            return [found]
    return ["corepack", "pnpm"]


def patch_files(patch: Path) -> list[str]:
    return sorted(set(re.findall(r"^diff --git a/(\S+)", read(patch), flags=re.MULTILINE)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-suite", action="store_true", help="跳过 P3（不跑上游套件，只查补丁与纪律）")
    args = ap.parse_args()

    # ── P1 探活 ──
    record((UPSTREAM / "package.json").is_file(), f"P1a 上游 fork 存在: {UPSTREAM}")
    record((UPSTREAM / "node_modules").is_dir() and DESKTOP_TESTS.is_dir(),
           "P1b 依赖已装且 apps/desktop/tests 就位")
    if not DESKTOP_TESTS.is_dir():
        return finish()

    # ── P2 差异集 07 补丁 ──
    files_07 = patch_files(PATCH_07)
    record(files_07 == EXPECTED_07,
           f"P2 差异集 07 补丁枚举 = {len(files_07)} 文件（期望 {len(EXPECTED_07)}）")

    # ── P3 上游桌面壳套件全绿 ──
    if args.no_suite:
        info("P3 已按 --no-suite 跳过")
    else:
        proc = run([*pnpm(), "exec", "vitest", "run", "--project", "thread-safe", SUITE_GLOB], UPSTREAM)
        output = (proc.stdout or "") + (proc.stderr or "")
        files_line = next((ln.strip() for ln in reversed(output.splitlines())
                           if ln.strip().startswith("Test Files ")), "")
        tests_line = next((ln.strip() for ln in reversed(output.splitlines())
                           if ln.strip().startswith("Tests ")), "")
        record(proc.returncode == 0 and "failed" not in (tests_line + files_line),
               f"P3 上游桌面壳套件全绿（{files_line or '无文件行'}；{tests_line or '无汇总行'}）")

    # ── P4 测试纪律未被削弱 ──
    deleted = [p for p in git("diff", "--diff-filter=D", "--name-only", "HEAD", "--", SUITE_GLOB).splitlines()
               if p.strip()]
    record(not deleted, f"P4a 测试文件未被删除（命中: {deleted or '无'}）")
    diff_text = git("diff", "HEAD", "--", SUITE_GLOB)
    added_skips = [ln for ln in diff_text.splitlines()
                   if ln.startswith("+") and not ln.startswith("+++") and re.search(r"\.(?:skip|todo)\(", ln)]
    record(not added_skips, f"P4b 未新增 skip/todo（命中: {len(added_skips)}）")
    changed_specs = [p for p in (EXPECTED_07 if files_07 == EXPECTED_07 else [])
                     if p.endswith((".spec.ts", ".spec.tsx"))]
    case_changes = []
    for rel in changed_specs:
        for line in git("diff", "HEAD", "--", rel).splitlines():
            if line[:1] in "+-" and not line.startswith(("+++", "---")) \
                    and re.search(r"(?<![\w$])(?:it|test|describe)(?:\.\w+)?\(", line):
                case_changes.append(f"{rel}:{line[:1]}{line[1:].strip()[:50]}")
    record(not case_changes, f"P4c 用例声明未增删（改动 spec: {len(changed_specs)}；命中: {case_changes or '无'}）")

    # ── P5 品牌期望留在原地（只允许登记的自洽夹具）──
    grep = run(["rg", "-l", BRAND, str(DESKTOP_TESTS)], UPSTREAM)
    hits = sorted({ln.strip().replace("\\", "/").replace(f"{UPSTREAM.as_posix()}/", "")
                   for ln in grep.stdout.splitlines() if ln.strip()})
    unexpected = [h for h in hits if h not in FIXTURE_ALLOWLIST]
    record(not unexpected,
           f"P5 品牌串仅存于登记的自洽夹具（命中文件 {len(hits)}，越界: {unexpected or '无'}）")
    info(f"登记的自洽夹具（不改，理由见交付说明 §4）：{len(FIXTURE_ALLOWLIST)} 个文件")

    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
