#!/usr/bin/env python
"""T-107 门禁：客户端品牌残留与打包冒烟产品名（差异集 03 + 04）。

断言：
  P1  探活：上游 fork 存在且依赖已装
  P2  差异集 03 / 04 / 05 / 06 补丁存在，且文件枚举与登记一致
  P3  客户端源码品牌残留 = 0（5 个客户端包的 src）
  P4  客户端上游期望文件品牌残留 = 0（5 个客户端包的 tests）
  P5  关于页 applicationName = WorkNexus-DSH（白名单 1.4「关于页文案」）
  P5b 反馈入口目标站点 = https://example.com/（差异集 06，企业侧页面入口）
  P6  产品名单一来源：常量模块（.mjs + .d.mts）与打包配置/冒烟脚本一致
  P7  品牌相关上游 spec 全绿（thread-safe；5 个 spec，0 failed）
  P8  打包产物 app.asar 存在
  P9  客户端可见面零残留：全部 `dsh-client-ui-*` 构建产物、Web 前端 index.html、关于页字面量 = 0
  P10 app.asar 残余命中全部落在已登记类别（K1~K5 + Web/PWA 清单名称），且注释类去注释后为 0
  P11 负向：客户端套件未新增 skip / todo

前置：`python scripts/pack_enterprise.py`，并在上游树运行一次
      `pnpm run package:desktop:win:x64:unsigned`（约 9 分钟）产出 app.asar。
用法：python scripts/verify_t107_client_brand.py [--no-artifact]   # --no-artifact 跳过 P8~P10
退出码：全部 [OK] 为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
PATCH_03 = REPO / "patches" / "diffset-03-client-brand.patch"
PATCH_04 = REPO / "patches" / "diffset-04-packaged-smoke-name.patch"
PATCH_05 = REPO / "patches" / "diffset-05-client-visible-brand.patch"
PATCH_06 = REPO / "patches" / "diffset-06-feedback-entry.patch"
ASAR = (UPSTREAM / "apps" / "desktop" / ".desktop-build" / "targets" / "win-x64"
        / "unsigned-artifacts" / "win-unpacked" / "resources" / "app.asar")

# 自有品牌落点：4 个客户端包
OWNED_PACKAGES = (
    "ui-brand-official",
    "ui-plugin-manager",
    "ui-settings-account",
    "ui-settings-models",
    "ui-sidebar-documentpreview",
)
OWNED_SRC = tuple(f"packages/client/{p}/src" for p in OWNED_PACKAGES)
OWNED_TESTS = tuple(f"packages/client/{p}/tests" for p in OWNED_PACKAGES)

# 差异集 03 的权威枚举（24 条）：6 个源码 + 16 个上游期望文件 + 2 个关于页文件
EXPECTED_03_SRC = [
    "apps/desktop/src/main.ts",
    "apps/desktop/tests/expected/about-panel.json",
    "packages/client/ui-brand-official/src/client/Brand.tsx",
    "packages/client/ui-brand-official/src/client/index.ts",
    "packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx",
    "packages/client/ui-settings-account/src/client/locales.ts",
    "packages/client/ui-settings-account/src/client/locales/onboarding.ts",
    "packages/client/ui-settings-models/src/client/locales.ts",
    "packages/client/ui-settings-models/tests/welcome-notice.client.spec.tsx",
    "packages/client/ui-sidebar-documentpreview/src/client/office/locales.ts",
]
EXPECTED_TXT_DIR = "packages/client/ui-settings-account/tests/expected/"
EXPECTED_03_TXT = [
    "account-signed-out-en.txt", "account-signed-out-zh.txt",
    "onboarding-credit-en.txt", "onboarding-credit.txt",
    "onboarding-process-en.txt", "onboarding-process.txt",
    "onboarding-purpose-en.txt", "onboarding-purpose.txt",
    "onboarding-welcome-en.txt", "onboarding-welcome.txt",
    "platform-error-en.txt", "platform-error-zh.txt",
    "platform-header-en.txt", "platform-header-zh.txt",
]
EXPECTED_03 = sorted(EXPECTED_03_SRC + [EXPECTED_TXT_DIR + n for n in EXPECTED_03_TXT])

# 差异集 04 的权威枚举（4 条）
EXPECTED_04 = sorted([
    "apps/desktop/scripts/desktop-product-name.d.mts",
    "apps/desktop/scripts/desktop-product-name.mjs",
    "apps/desktop/scripts/electron-builder-config.mjs",
    "apps/desktop/scripts/smoke-packaged-runtime.ts",
])

# 差异集 05 的权威枚举（7 条）：构建期标题常量 + 插件安全文案 + 其上游期望值
EXPECTED_05 = sorted([
    "apps/web/tests/expected/plugin-install-cancel/cancelled.expected.md",
    "apps/web/tests/expected/plugin-install-github/another-way.expected.md",
    "apps/web/tests/expected/plugin-install-github/mirror.expected.md",
    "packages/client/ui-plugin-manager/src/client/locales.ts",
    "scripts/client-build-environment.client.spec.ts",
    "scripts/client-build-environment.ts",
    "scripts/dev-web.spec.ts",
])

# 差异集 06 的权威枚举（4 条）：账号菜单「意见反馈」外链的目标站点 + 其上游期望值 + 2 个上游 README
EXPECTED_06 = sorted([
    "packages/client/ui-settings-account/src/contact-config.ts",
    "packages/client/ui-settings-account/tests/contact-url.client.spec.ts",
    "packages/client/ui-settings-account/README.md",
    "packages/client/ui-settings-account/README.zh.md",
])

# 反馈入口的目标站点（企业站点）
FEEDBACK_ORIGIN = "https://example.com/"

# 品牌相关上游 spec（T-107 范围；其余 apps/desktop/tests 期望由 T-108 负责）
# 注：`scripts/dev-web.spec.ts` 有 1 条用例在本机因 Windows 符号链接权限（EPERM）失败，
# 与品牌无关，故不纳入门禁；其品牌期望值仍随差异集 05 更新。
BRAND_SPECS = [
    "packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx",
    "packages/client/ui-settings-account/tests/account.client.spec.tsx",
    "packages/client/ui-settings-account/tests/desktop-onboarding.client.spec.tsx",
    "packages/client/ui-settings-models/tests/welcome-notice.client.spec.tsx",
    "scripts/client-build-environment.client.spec.ts",
]

NEEDLE = b"DeepSeek Harness"

# 客户端可见面：这些路径一旦出现品牌命中即 [FAIL]（差异集 03 + 05 的关闭对象）。
# 注意：只算**构建产物**（lib/ dist/）与 Web 入口 HTML；包自带的 README/package.json
# 属随包原样的 npm 元数据与文档（K2/K3），不在可见面内。
VISIBLE_SURFACE_PATTERNS = (
    re.compile(r"^dsh/node_modules/@deepseek-ai/dsh-client-ui-[^/]+/(lib|dist)/"),
    re.compile(r"^dsh/node_modules/@deepseek-ai/dsh-web-frontend/dist/index\.html$"),
)


def is_visible_surface(rel: str) -> bool:
    return any(pattern.match(rel) for pattern in VISIBLE_SURFACE_PATTERNS)

# app.asar 残余命中的登记类别（先匹配先归类；未落入任何类别即 [FAIL]）
# K1 注释类：去注释后必须为 0（B-3 裁决：不改上游 JSDoc 注释）
# K2 包元数据 / K3 包文档 / K4 技能参考文档：随包原样的 npm 元数据与文档
# K5 上游运行时文案：CLI 描述、系统提示词、错误消息（属 N-1 禁止改动区）
# K6 Web/PWA 清单名称：静态 `manifest.webmanifest` 的产品名，桌面发行版不加载该 Web 前端，
#    经决策人「按建议执行」明确**不改**（见交付说明 §8.3）
RESIDUAL_CATEGORIES = [
    ("K1 注释类", r"^(dsh/node_modules/@deepseek-ai/dsh-home-paths/lib/index\.js|lib/main\.js)$"),
    ("K2 包元数据", r"^(dsh/)?node_modules/@deepseek-ai/[^/]+/package\.json$"),
    ("K3 包文档", r"^dsh/node_modules/@deepseek-ai/[^/]+/README(\.zh)?\.md$"),
    ("K4 技能参考文档", r"^dsh/node_modules/@deepseek-ai/dsh-agent-preset/skills/.*$"),
    ("K6 Web/PWA 清单名称（登记不改）",
     r"^dsh/node_modules/@deepseek-ai/dsh-web-frontend/dist/manifest\.webmanifest$"),
    ("K5 上游运行时文案", r"^dsh/node_modules/@deepseek-ai/[^/]+/(lib|dist)/.*\.(js|mjs|cjs)$"),
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


def grep_paths(roots: tuple[str, ...], pattern: str) -> list[str]:
    """在给定目录下检索 pattern，返回命中的仓库相对路径。"""
    args = ["rg", "-l", pattern, *roots]
    proc = run(args, REPO)
    if proc.returncode not in (0, 1):
        # rd 不可用或目录缺失时退化为 Python 遍历
        hits = []
        for root in roots:
            base = REPO / root
            for path in base.rglob("*") if base.exists() else []:
                if path.is_file() and pattern in read(path):
                    hits.append(path.relative_to(REPO).as_posix())
        return sorted(set(hits))
    return sorted({line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()})


def patch_files(patch: Path) -> list[str]:
    return sorted(set(re.findall(r"^diff --git a/(\S+)", read(patch), flags=re.MULTILINE)))


def asar_entries(path: Path) -> tuple[list[tuple[str, int, int]], bytes]:
    raw = path.read_bytes()
    header_size = struct.unpack("<I", raw[4:8])[0]
    json_len = struct.unpack("<I", raw[12:16])[0]
    header = json.loads(raw[16:16 + json_len].decode("utf-8"))
    base = 8 + header_size
    entries: list[tuple[str, int, int]] = []

    def walk(node: dict, prefix: str) -> None:
        for name, value in node.get("files", {}).items():
            child = f"{prefix}/{name}"
            if "files" in value:
                walk(value, child)
            elif "offset" in value:
                entries.append((child.lstrip("/"), base + int(value["offset"]), int(value["size"])))

    walk(header, "")
    return entries, raw


def strip_comments(blob: bytes) -> str:
    text = blob.decode("utf-8", "replace")
    text = re.sub(r"/\*[\s\S]*?\*/", " ", text)
    return re.sub(r"(?m)//[^\n]*", " ", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-artifact", action="store_true", help="跳过 P8~P10（未出包时）")
    args = ap.parse_args()

    # ── P1 探活 ──
    record((UPSTREAM / ".git").exists(), f"P1a 上游 fork 仓库存在: {UPSTREAM}")
    vitest = UPSTREAM / "node_modules" / ".bin" / "vitest"
    record(vitest.exists() or (UPSTREAM / "node_modules").exists(),
           "P1b 上游依赖已装（node_modules 存在）")
    if not (UPSTREAM / ".git").exists():
        return finish()

    # ── P2 差异集补丁 ──
    files_03 = patch_files(PATCH_03)
    record(files_03 == EXPECTED_03,
           f"P2a 差异集 03 补丁枚举 = {len(files_03)} 文件（期望 {len(EXPECTED_03)}）")
    files_04 = patch_files(PATCH_04)
    record(files_04 == EXPECTED_04,
           f"P2b 差异集 04 补丁枚举 = {len(files_04)} 文件（期望 {len(EXPECTED_04)}）")
    files_05 = patch_files(PATCH_05)
    record(files_05 == EXPECTED_05,
           f"P2c 差异集 05 补丁枚举 = {len(files_05)} 文件（期望 {len(EXPECTED_05)}）")
    files_06 = patch_files(PATCH_06)
    record(files_06 == EXPECTED_06,
           f"P2d 差异集 06 补丁枚举 = {len(files_06)} 文件（期望 {len(EXPECTED_06)}）")

    # ── P5b 反馈入口目标站点（差异集 06）──
    contact_config = read(UPSTREAM / "packages/client/ui-settings-account/src/contact-config.ts")
    record(f"default('{FEEDBACK_ORIGIN}')" in contact_config
           and "feishu.cn" not in contact_config,
           f"P5b 反馈入口目标站点 = {FEEDBACK_ORIGIN}（无上游飞书问卷残留）")

    # ── P3 客户端源码零残留 ──
    src_hits = grep_paths(OWNED_SRC, "DeepSeek Harness")
    record(not src_hits, f"P3 客户端源码品牌残留 = {len(src_hits)}（命中: {src_hits or '无'}）")

    # ── P4 客户端期望文件零残留 ──
    test_hits = grep_paths(OWNED_TESTS, "DeepSeek Harness")
    record(not test_hits, f"P4 客户端期望文件品牌残留 = {len(test_hits)}（命中: {test_hits or '无'}）")

    # ── P5 关于页 ──
    main_ts = read(UPSTREAM / "apps/desktop/src/main.ts")
    about = re.search(r"setAboutPanelOptions\(\{[\s\S]*?\}\)", main_ts)
    record(about is not None and "applicationName: 'WorkNexus-DSH'" in about.group(0),
           "P5 关于页 applicationName = WorkNexus-DSH（白名单 1.4）")

    # ── P6 产品名单一来源 ──
    product_mjs = read(UPSTREAM / "apps/desktop/scripts/desktop-product-name.mjs")
    product_d = read(UPSTREAM / "apps/desktop/scripts/desktop-product-name.d.mts")
    cfg = read(UPSTREAM / "apps/desktop/scripts/electron-builder-config.mjs")
    smoke = read(UPSTREAM / "apps/desktop/scripts/smoke-packaged-runtime.ts")
    record("export const DESKTOP_PRODUCT_NAME = 'WorkNexus-DSH'" in product_mjs
           and "DESKTOP_PRODUCT_NAME: 'WorkNexus-DSH'" in product_d
           and "productName: DESKTOP_PRODUCT_NAME" in cfg
           and "DESKTOP_PRODUCT_NAME" in smoke
           and "DeepSeek Harness" not in smoke,
           "P6 产品名单一来源（.mjs 常量 + .d.mts 声明 + 配置/冒烟脚本引用，冒烟脚本无上游名）")

    # ── P7 品牌相关上游 spec 全绿 ──
    proc = run([*pnpm(), "exec", "vitest", "run", "--project", "thread-safe", *BRAND_SPECS], UPSTREAM)
    output = (proc.stdout or "") + (proc.stderr or "")
    summary = next((ln.strip() for ln in reversed(output.splitlines()) if ln.strip().startswith("Tests ")), "")
    files_line = next((ln.strip() for ln in reversed(output.splitlines()) if ln.strip().startswith("Test Files ")), "")
    record(proc.returncode == 0 and "failed" not in summary and "passed" in summary,
           f"P7 品牌相关上游 spec 全绿（{files_line or '无文件行'}；{summary or '无汇总行'}）")

    # ── P8~P10 打包产物核验 ──
    if args.no_artifact:
        info("P8~P10 已按 --no-artifact 跳过（需先出包）")
        return finish()

    record(ASAR.exists(), f"P8 打包产物 app.asar 存在（{ASAR.stat().st_size if ASAR.exists() else 0} 字节）")
    if not ASAR.exists():
        return finish()

    entries, raw = asar_entries(ASAR)
    hits = []
    for rel, offset, size in entries:
        blob = raw[offset:offset + size]
        count = blob.count(NEEDLE)
        if count:
            hits.append((rel, count, strip_comments(blob).count("DeepSeek Harness")))

    # P9 客户端可见面零残留
    visible_hits = [rel for rel, _, _ in hits if is_visible_surface(rel)]
    about_literal = b'applicationName: "DeepSeek Harness"' in raw
    record(not visible_hits and not about_literal,
           f"P9 客户端可见面零残留（客户端 UI 构建产物 / Web index.html 命中 {len(visible_hits)}"
           f"{'：' + str(visible_hits) if visible_hits else ''}；关于页字面量 = {about_literal}）")

    # P10 残余命中逐类归入登记类别
    per_category: Counter[str] = Counter()
    per_category_hits: Counter[str] = Counter()
    unclassified: list[str] = []
    comment_leaks: list[str] = []
    for rel, count, code_count in hits:
        for name, pattern in RESIDUAL_CATEGORIES:
            if re.match(pattern, rel):
                per_category[name] += 1
                per_category_hits[name] += count
                if name.startswith("K1") and code_count:
                    comment_leaks.append(f"{rel}({code_count})")
                break
        else:
            unclassified.append(rel)
    record(not unclassified and not comment_leaks,
           f"P10 app.asar 残余命中全部归入登记类别（未分类: {unclassified or '无'}；"
           f"K1 去注释后泄漏: {comment_leaks or '无'}）")
    info(f"app.asar 命中文件 {len(hits)} / 命中 {sum(c for _, c, _ in hits)} 处（基线 254）")
    for name, _ in RESIDUAL_CATEGORIES:
        info(f"  {name}: {per_category[name]} 文件 / {per_category_hits[name]} 处")

    # ── P11 负向：未新增 skip/todo ──
    diff_text = git("diff", "HEAD", "--", *OWNED_TESTS)
    added_skips = [ln for ln in diff_text.splitlines()
                   if ln.startswith("+") and not ln.startswith("+++")
                   and re.search(r"\.(?:skip|todo)\(", ln)]
    record(not added_skips, f"P11 客户端套件未新增 skip/todo（命中: {len(added_skips)}）")

    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
