#!/usr/bin/env python
"""差异集 12 门禁：会话首屏品牌面（品牌标志 + 口号）。

背景：客户端「新会话」首屏（blank-session hero）此前显示上游鲸鱼标志与上游口号
（`探索未至之境` / `Into the Unknown`）。hero 标志由 `conversation.hero.brand.mark`
插槽渲染，该插槽是 `kind: single` / `scope: root` / `replaceRisk: none` 且**无占用者**，
因此企业侧在品牌包 `ui-brand-official` 里注册占用即可，**不改上游组件 `EmptyHero.tsx`**
（上游动画鲸鱼仍作为未占用时的回退保留）。

断言：
  P1  差异集 12 补丁存在，权威枚举 = 14 个上游文件
  P2  品牌包注册 hero 插槽占用，且与侧栏共用同一枚标志素材（单一来源）
  P3  上游 hero 组件零改动：`EmptyHero.tsx` 仍以鲸鱼为回退，品牌包不再引用 `FishLogo`
  P4  行为：品牌包与 hero 文案的上游用例全绿（真实执行插槽注册与渲染）
  P5  hero 口号：zh = 智能协作中心 / en = Intelligent Collaboration Hub，旧上游口号归零
  P6  期望同步：14 个文件中的期望资产不再含旧上游口号
P7  上游差异集条目数 = 120（01~12 的 106 + 13 新增 13 + 14 新增 1；2026-10-12 基线迁移后差异集 07 增补 project-manager.spec.ts）
  P8  补丁可逆重放（`git apply --reverse --check`）

用法：python scripts/verify_diffset12_hero_brand.py [--no-suite]
退出码：全部通过为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
PATCH = REPO / "patches" / "diffset-12-hero-brand.patch"
LOCALES = "packages/client/ui-conversation/src/client/locales.ts"
HERO_COMPONENT = "packages/client/ui-conversation/src/client/skeleton/EmptyHero.tsx"
BRAND_INDEX = "packages/client/ui-brand-official/src/client/index.ts"
BRAND_MARK = "packages/client/ui-brand-official/src/client/Brand.tsx"

ZH_HEADLINE = "智能协作中心"
EN_HEADLINE = "Intelligent Collaboration Hub"
OLD_ZH_HEADLINE = "探索未至之境"
OLD_EN_HEADLINE = "Into the Unknown"

EXPECTED_FILES = sorted([
    LOCALES,
    "packages/client/ui-conversation/tests/skeleton.client.spec.tsx",
    "apps/web/tests/connection-recovery.e2e.ts",
    "apps/web/tests/details-session-lifecycle.e2e.ts",
    "apps/web/tests/goal-command-presentation.e2e.ts",
    "apps/web/tests/hmr-live.e2e.ts",
    "apps/web/tests/lifecycle-chrome.e2e.ts",
    "apps/web/tests/session-replay-reload.e2e.ts",
    "apps/web/tests/startup-auto-selection.e2e.ts",
    "snapshots/web/fresh-round-trip/blank-reload.expected.md",
    "snapshots/web/lifecycle-chrome/hero.expected.md",
    "snapshots/web/lifecycle-chrome/plan-active-zh.expected.md",
    "snapshots/web/lifecycle-chrome/plan-active.expected.md",
    "snapshots/web/voice-input/ui.expected.md",
])

# 期望资产（非源码）逐字节断言旧口号已清除
EXPECTATION_FILES = [p for p in EXPECTED_FILES if p != LOCALES]
EXPECTED_DIFFSET_PATHS = 120

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def read(rel: str) -> str:
    path = UPSTREAM / rel
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(UPSTREAM), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def changed_paths() -> list[str]:
    tracked = [line.strip() for line in git("diff", "--name-only", "HEAD").stdout.splitlines() if line.strip()]
    untracked = [line.strip() for line in git("ls-files", "--others", "--exclude-standard").stdout.splitlines()
                 if line.strip()]
    return sorted(set(tracked + untracked))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-suite", action="store_true", help="跳过上游用例回归")
    args = parser.parse_args()

    print("=" * 60)
    print("差异集 12 门禁：会话首屏品牌面（品牌标志 + 口号）")
    print("=" * 60)

    # ── P1 补丁枚举 ──
    text = PATCH.read_text(encoding="utf-8", errors="replace") if PATCH.exists() else ""
    files = sorted({m.group(1) for m in re.finditer(r"^diff --git a/(.+?) b/", text, re.MULTILINE)})
    record(bool(text) and files == EXPECTED_FILES,
           f"P1 差异集 12 权威枚举 = {len(files)} 文件（期望 {len(EXPECTED_FILES)}）")

    # ── P2 品牌包占用 hero 插槽 ──
    brand_index = read(BRAND_INDEX)
    record("conversation.hero.brand.mark" in brand_index
           and "ctx.slots.register({ name: 'conversation.hero.brand.mark' }, BrandMark)" in brand_index,
           "P2 品牌包在 official 档注册 `conversation.hero.brand.mark` 占用（BrandMark）")
    record("import type {} from '@deepseek-ai/dsh-client-ui-conversation/client'" in brand_index,
           "P2 插槽名并入类型表（类型侧引用 conversation 契约）")
    brand_mark = read(BRAND_MARK)
    record(brand_mark.count("data:image/png;base64,") == 1
           and brand_mark.count("const BRAND_MARK_DATA_URI = 'data:image/png;base64,'") == 1
           and brand_mark.count("href={BRAND_MARK_DATA_URI}") == 1
           and "export function BrandMark({ size, className }: HeroBrandMarkOwnerProps)" in brand_mark,
           "P2 标志素材单一来源：侧栏与 hero 共用同一枚 PNG data URI 常量")
    record("return <BrandMark size={size} />" in brand_mark,
           "P2 侧栏标志委托给同一组件（不复制素材）")

    # ── P3 上游 hero 组件零改动 ──
    hero = read(HERO_COMPONENT)
    record("fallback: <HeroFish hovering={hovering} />" in hero
           and "FISH_LOGO_PATH" in hero,
           "P3 上游 `EmptyHero.tsx` 未改：hero 仍以动画鲸鱼为回退")
    record("FishLogo" not in brand_mark and "FISH_LOGO_PATH" not in brand_mark,
           "P3 品牌包不再引用上游鲸鱼标志")

    # ── P4 上游用例回归 ──
    if args.no_suite:
        print("[跳过] P4 上游用例（--no-suite）")
    else:
        vitest = UPSTREAM / "node_modules" / ".bin" / ("vitest.CMD" if sys.platform == "win32" else "vitest")
        if not vitest.exists():
            record(False, f"P4 找不到上游 vitest：{vitest}")
        else:
            proc = subprocess.run(
                [str(vitest), "run",
                 "packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx",
                 "packages/client/ui-conversation/tests/skeleton.client.spec.tsx"],
                cwd=str(UPSTREAM), capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            out = proc.stdout + proc.stderr
            record(proc.returncode == 0 and re.search(r"Tests\s+\d+ passed", out) is not None
                   and " failed" not in out,
                   "P4 品牌包与 hero 文案上游用例全绿（插槽注册 + 渲染断言）")

    # ── P5 hero 口号 ──
    locales = read(LOCALES)
    record(f"'hero.headline': '{ZH_HEADLINE}'" in locales
           and f"'hero.headline': '{EN_HEADLINE}'" in locales,
           f"P5 hero 口号 = {ZH_HEADLINE} / {EN_HEADLINE}")
    record(OLD_ZH_HEADLINE not in locales and OLD_EN_HEADLINE not in locales,
           "P5 上游口号（探索未至之境 / Into the Unknown）在文案源中归零")

    # ── P6 期望资产同步 ──
    stale = [rel for rel in EXPECTATION_FILES
             if OLD_ZH_HEADLINE in read(rel) or OLD_EN_HEADLINE in read(rel)]
    record(not stale, f"P6 {len(EXPECTATION_FILES)} 个期望资产已就地同步（残留旧口号: {stale or '无'}）")

    # ── P7 差异集条目数 ──
    paths = changed_paths()
    record(len(paths) == EXPECTED_DIFFSET_PATHS,
           f"P7 上游差异集条目数 = {len(paths)}（01~12 的 105 + 13 新增 13 + 14 新增 1）")
    record(all(path in paths for path in EXPECTED_FILES),
           "P7 差异集 12 的 14 个文件都在改动集内")

    # ── P8 补丁可逆重放 ──
    check = git("apply", "--reverse", "--check", "--binary", str(PATCH))
    record(check.returncode == 0,
           f"P8 差异集 12 补丁可逆重放（worktree 即补丁落地态）：{check.stderr.strip() or 'ok'}")

    failures = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failures)} [OK] / {len(failures)} [FAIL]")
    for detail in failures:
        print(f"  - {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
