#!/usr/bin/env python
"""T-021 门禁：差异集落地——品牌与产品标识。

断言：
  G1  上游 fork 仓库存在且基线提交在案
  G2  改动范围 ⊆ 品牌白名单（T-002 §3，含 T-021 增补的 locale.ts 等条目）
  G3  负向：未触及核心行为文件（会话执行/工具调用/插件加载/更新算法/恢复策略/安全基线/preload/凭据/诊断）
  G4  负向：许可与合规文件与基线逐字节一致
  G5  品牌字符串已替换（locale.ts 中 "DeepSeek Harness" 归零；打包配置为 WorkNexus-DSH）
  G6  占位图标结构有效（PNG 签名/尺寸、ICO 头），且可由脚本确定性重生成
  G7  差异补丁已导出且包含三类落点
可选（--full）：
  G8  `pnpm --filter @deepseek-ai/dsh-desktop run build` 退出码 0

用法：
  python scripts/verify_t021_brand.py
  python scripts/verify_t021_brand.py --full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
PATCH = REPO / "patches" / "diffset-01-brand.patch"

# T-002 §3 白名单中属于本次品牌差异的条目（+ T-021 增补，见交付说明 §4）
WHITELIST = [
    "README.md",
    "WORKNEXUS-RELEASE-NOTES.md",
    "apps/desktop/resources/",
    "apps/desktop/scripts/electron-builder-config.mjs",
    "apps/desktop/src/locale.ts",
    # 差异集 02「发行物打包集成」（DC-6 批准，2026-09-29）：包集闭包与企业 profile 预置 bundle 清单。
    # 命中 T-002 §3 白名单 3.1「预置 bundle 清单」；属白名单外上游文件改动，经 DC-6 评审通过。
    "apps/desktop/scripts/prepare-package-set.ts",
    "apps/desktop/src/project-manager.ts",
    # 差异集 04「打包后冒烟脚本产品名」（DC-6 批准）：产品名单一来源 + 冒烟脚本跟随。
    "apps/desktop/scripts/desktop-product-name.mjs",
    "apps/desktop/scripts/desktop-product-name.d.mts",
    "apps/desktop/scripts/smoke-packaged-runtime.ts",
    # 差异集 03「客户端品牌残留」（DC-6 批准）：品牌组件 + 客户端文案
    "packages/client/ui-brand-official/src/client/Brand.tsx",
    "packages/client/ui-settings-account/src/client/locales.ts",
    "packages/client/ui-settings-account/src/client/locales/onboarding.ts",
    "packages/client/ui-settings-models/src/client/locales.ts",
    "packages/client/ui-sidebar-documentpreview/src/client/office/locales.ts",
    # 差异集 03（T-107 S3）：品牌文案牵动的上游**期望文件**就地更新（DC-7 / DS-3 口径）。
    # 只改期望值、不改测试逻辑，AGENTS §6「上游既有测试不得删除或跳过」仍然成立。
    "packages/client/ui-brand-official/src/client/index.ts",
    "packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx",
    "packages/client/ui-settings-models/tests/welcome-notice.client.spec.tsx",
    "packages/client/ui-settings-account/tests/expected/",
    # 差异集 03（T-107 S5 发现）：关于页（白名单 1.4「关于页文案」）的 `applicationName`
    # 是桌面壳内硬编码的品牌字面量，只改这一行；规范文件为 main.ts，故从 FORBIDDEN 收窄。
    "apps/desktop/src/main.ts",
    "apps/desktop/tests/expected/about-panel.json",
    # 差异集 05「客户端可见品牌面」（2026-09-30 决策人「按建议执行」批准）：
    # 构建期标题常量（窗口标题的根因，白名单外共享构建脚本）+ 插件安装安全文案 + 其上游期望值。
    "scripts/client-build-environment.ts",
    "scripts/client-build-environment.client.spec.ts",
    "scripts/dev-web.spec.ts",
    "packages/client/ui-plugin-manager/src/client/locales.ts",
    "apps/web/tests/expected/plugin-install-github/mirror.expected.md",
    "apps/web/tests/expected/plugin-install-cancel/cancelled.expected.md",
    "apps/web/tests/expected/plugin-install-github/another-way.expected.md",
    # 差异集 06「反馈入口企业站点化」（2026-09-30 决策人指令）：账号菜单「意见反馈」外链的目标站点
    #（白名单「企业侧页面入口」）+ 其上游期望值就地更新（DC-7 口径）。
    "packages/client/ui-settings-account/src/contact-config.ts",
    "packages/client/ui-settings-account/tests/contact-url.client.spec.ts",
    # 差异集 06 扩项（T-108 顺手同步，2026-09-30）：上游包 README 不再声称「飞书问卷」。
    "packages/client/ui-settings-account/README.md",
    "packages/client/ui-settings-account/README.zh.md",
    # 差异集 07「桌面壳测试期望同步」（T-108，DC-7 / DS-3 口径）：由差异集 01/02/03 牵动的
    # `apps/desktop/tests/**` 期望值与内联断言就地更新（23 文件；只改期望值，用例声明零增删）。
    "apps/desktop/tests/background-notice.spec.ts",
    "apps/desktop/tests/installer-packaging.spec.ts",
    "apps/desktop/tests/macos-signature.spec.ts",
    "apps/desktop/tests/main-startup.spec.ts",
    "apps/desktop/tests/quit-confirmation.spec.ts",
    "apps/desktop/tests/tray.spec.ts",
    "apps/desktop/tests/windows-update-publisher.spec.ts",
    "apps/desktop/tests/expected/application-menu-en-US.json",
    "apps/desktop/tests/expected/application-menu-zh-CN.json",
    "apps/desktop/tests/expected/fatal-",
    "apps/desktop/tests/expected/welcome/",
    # 差异集 01 追加（2026-09-30 决策人裁定）：`productName` 决定 `%APPDATA%` 目录名。
    "apps/desktop/package.json",
    # 差异集 08「更新源企业化」：生产 origin 改为环境驱动 + 两个模板补说明。
    "apps/desktop/scripts/desktop-auto-update-environment.mjs",
    "apps/desktop/tests/desktop-auto-update-environment.spec.ts",
    "apps/desktop/tests/desktop-upload-plan.spec.ts",
    "apps/desktop/tests/expected/latest-installer-uploads.json",
    "apps/desktop/.env.windows.example",
    "apps/desktop/.env.macos.example",
]

# 必须与基线逐字节一致的合规文件
FROZEN = [
    "LICENSE",
    "BRAND_GUIDELINES.md",
    "BRAND_GUIDELINES.zh.md",
    "BRAND_GUIDELINES.i18n.yaml",
    "THIRD_PARTY_NOTICES.md",
]

# 负向断言：这些路径一旦出现在差异里即视为越界
FORBIDDEN = [
    "apps/desktop/src/preload-",
    "apps/desktop/src/update-",
    "apps/desktop/src/mandatory-update",
    "apps/desktop/src/fatal-recovery.ts",
    "apps/desktop/src/crash-report.ts",
    "apps/desktop/src/host-process.ts",
    "apps/desktop/src/runtime-tree.ts",
    "packages/",
    "apps/web/",
    "vendor/",
]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(UPSTREAM), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def changed_paths() -> list[str]:
    out = git("diff", "--name-only", "HEAD")
    paths = [line.strip() for line in out.splitlines() if line.strip()]
    # 未跟踪的新文件也计入差异
    untracked = git("ls-files", "--others", "--exclude-standard")
    paths += [line.strip() for line in untracked.splitlines() if line.strip()]
    return sorted(set(paths))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    record((UPSTREAM / ".git").exists(), f"上游 fork 仓库存在: {UPSTREAM}")
    if not (UPSTREAM / ".git").exists():
        return finish()
    head = git("log", "--oneline", "-n", "1").strip()
    record(bool(head), f"基线提交在案: {head}")

    paths = changed_paths()
    record(bool(paths), f"差异集条目数 = {len(paths)}")

    outside = [p for p in paths if not any(p == w or p.startswith(w) for w in WHITELIST)]
    record(not outside, f"G2 改动全部落在品牌白名单内（越界: {outside or '无'}）")

    # FORBIDDEN 的 `packages/` 是 N-1~N-9 核心行为区的通配禁止；差异集 03（DC-6 批准）的
    # 品牌落点本就在 `packages/client/**`（白名单 1.1/1.2/1.3），故白名单内的路径豁免该通配，
    # 核心行为包（agent / skill / boot / cordis-plugin-loader 等）仍被禁止。
    # 白名单命中按与 G2 相同的前缀规则判定（差异集 03 的 `tests/expected/` 是目录前缀）。
    forbidden = [p for p in paths
                 if any(f in p for f in FORBIDDEN)
                 and not any(p == w or p.startswith(w) for w in WHITELIST)]
    record(not forbidden, f"G3 未触及核心行为文件（命中: {forbidden or '无'}）")

    frozen_bad = []
    for rel in FROZEN:
        base = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=str(UPSTREAM),
                              capture_output=True).stdout
        cur = (UPSTREAM / rel).read_bytes() if (UPSTREAM / rel).exists() else b""
        if hashlib.sha256(base).hexdigest() != hashlib.sha256(cur).hexdigest():
            frozen_bad.append(rel)
    record(not frozen_bad, f"G4 合规文件与基线逐字节一致（不一致: {frozen_bad or '无'}）")

    locale_txt = (UPSTREAM / "apps/desktop/src/locale.ts").read_text(encoding="utf-8")
    cfg = (UPSTREAM / "apps/desktop/scripts/electron-builder-config.mjs").read_text(encoding="utf-8")
    # 差异集 04（T-107 S4）：产品名抽成常量模块，配置改为引用它；品牌断言随之落到常量模块上，
    # 判据强度不变（仍要求产品名字面量 = WorkNexus-DSH 且配置引用该常量）。
    product_module = (UPSTREAM / "apps/desktop/scripts/desktop-product-name.mjs").read_text(encoding="utf-8")
    g5 = (
        locale_txt.count("DeepSeek Harness") == 0
        and locale_txt.count("WorkNexus-DSH") >= 20
        and "productName: DESKTOP_PRODUCT_NAME" in cfg
        and "export const DESKTOP_PRODUCT_NAME = 'WorkNexus-DSH'" in product_module
        and "name: 'WorkNexus-DSH'" in cfg
        and "worknexus-dsh-\\${version}" in cfg
    )
    record(g5, "G5 品牌字符串已替换（locale.ts 归零、打包配置为 WorkNexus-DSH）")

    # G9 收窄守卫：main.ts 从 FORBIDDEN 移出后，只允许「关于页 applicationName」这一处改动。
    main_diff = git("diff", "HEAD", "--", "apps/desktop/src/main.ts")
    main_lines = [ln for ln in main_diff.splitlines()
                  if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    record(len(main_lines) == 2
           and "DeepSeek Harness" in main_lines[0]
           and "WorkNexus-DSH" in main_lines[1],
           f"G9 关于页 applicationName 单点替换（main.ts 改动行 = {len(main_lines)}）")

    # G10 收窄守卫（差异集 05，白名单外共享构建脚本）：只允许「窗口标题常量」这一处改动。
    title_diff = git("diff", "HEAD", "--", "scripts/client-build-environment.ts")
    title_lines = [ln for ln in title_diff.splitlines()
                   if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    record(len(title_lines) == 2
           and "DeepSeek Harness" in title_lines[0]
           and "WorkNexus-DSH" in title_lines[1],
           f"G10 窗口标题常量单点替换（client-build-environment.ts 改动行 = {len(title_lines)}）")

    res = UPSTREAM / "apps" / "desktop" / "resources"
    icon_ok = True
    detail = []
    for name, size in (("icon.png", 512), ("icon-windows.png", 256), ("icon-macos.png", 512)):
        p = res / name
        b = p.read_bytes() if p.exists() else b""
        ok = b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) > 24 and struct.unpack(">II", b[16:24]) == (size, size)
        icon_ok &= ok
        detail.append(f"{name}={'ok' if ok else 'bad'}")
    ico = res / "tray-windows.ico"
    ib = ico.read_bytes() if ico.exists() else b""
    # 托盘 ICO 必须覆盖上游 render-tray-icon.ts 的 TRAY_ICON_SIZES（Windows 按显示缩放挑档，
    # 单档会导致高 DPI 下发虚 —— 上游 tray-icon.spec.ts 同样断言这 7 档）。
    tray_sizes = (16, 20, 24, 32, 40, 48, 64)
    ico_ok, ico_detail = False, "缺失"
    if len(ib) >= 6 + 16 * len(tray_sizes):
        reserved, image_type, count = struct.unpack("<HHH", ib[:6])
        entries, offset, edges = [], 6, []
        for _ in range(count):
            w, h, _colors, _reserved, _planes, _bits, size, pos = struct.unpack(
                "<BBBBHHII", ib[offset:offset + 16])
            offset += 16
            png = ib[pos:pos + size]
            edges.append(w or 256)
            entries.append((w or 256) == (h or 256) and png[:8] == b"\x89PNG\r\n\x1a\n"
                           and len(png) > 24 and struct.unpack(">II", png[16:24]) == (w or 256, h or 256))
        ico_ok = (reserved == 0 and image_type == 1 and count == len(tray_sizes)
                  and tuple(edges) == tray_sizes and all(entries))
        ico_detail = f"{count} 档 {edges}"
    record(icon_ok and ico_ok,
           f"G6 占位图标结构有效（{', '.join(detail)}, tray-windows.ico={ico_detail}）")

    if PATCH.exists():
        data = PATCH.read_bytes()
        # 逐文件枚举比对（子串命中会被 README 里提到的文件名误判：实测漏掉
        # WORKNEXUS-RELEASE-NOTES.md 时，README 的正文仍包含该文件名 —— 由 T-027 Y3/Y7 才暴露）。
        patch_paths = sorted(set(re.findall(r"^diff --git a/(\S+)", data.decode("utf-8", "replace"),
                                            flags=re.MULTILINE)))
        expected_01 = sorted([
            "README.md", "WORKNEXUS-RELEASE-NOTES.md",
            "apps/desktop/package.json",
            "apps/desktop/resources/icon-macos.png", "apps/desktop/resources/icon-macos.svg",
            "apps/desktop/resources/icon-windows.png", "apps/desktop/resources/icon-windows.svg",
            "apps/desktop/resources/icon.png", "apps/desktop/resources/icon.svg",
            "apps/desktop/resources/tray-windows.ico",
            "apps/desktop/scripts/electron-builder-config.mjs", "apps/desktop/src/locale.ts",
        ])
        record(patch_paths == expected_01,
               f"G7 差异补丁枚举 = {len(patch_paths)} 文件（期望 {len(expected_01)}；"
               f"{PATCH.stat().st_size} 字节）")
    else:
        record(False, f"G7 差异补丁缺失: {PATCH}")

    if args.full:
        env = dict(os.environ, ELECTRON_SKIP_BINARY_DOWNLOAD="1")
        r = subprocess.run(
            ["node", str(UPSTREAM / "node_modules" / "pnpm" / "bin" / "pnpm.mjs"),
             "--filter", "@deepseek-ai/dsh-desktop", "run", "build"],
            cwd=str(UPSTREAM), capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env, timeout=1800,
        )
        record(r.returncode == 0, f"G8 桌面端构建退出码 {r.returncode}")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for o, _ in RESULTS if o)
    bad = sum(1 for o, _ in RESULTS if not o)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
