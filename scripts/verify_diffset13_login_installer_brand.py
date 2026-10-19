#!/usr/bin/env python
"""差异集 13 门禁：登录界面与安装界面的品牌面。

背景：决策人在真机上发现两处**图形字标**仍是上游品牌：
  ① 安装界面 —— NSIS 品牌砖图 `apps/desktop/installer/assets/brand{,-2x,-dark,-dark-2x}.png`
     与 `uninstaller-sidebar.png`（鲸鱼 + `deepseek HARNESS`）；
  ② 首次登录界面 —— 欢迎窗 `apps/desktop/renderer/assets/welcome-brand.svg`（同一字标），
     由 `apps/desktop/src/client/WelcomePage.tsx` 以 `<img width=472 height=40>` 引用。

断言：
  P1  差异集 13 补丁存在，权威枚举 = 13 个上游文件
  P2  六个品牌素材存在、尺寸/像素格式与上游几何一致
  P3  素材可由 `scripts/make_brand_assets.ps1` 确定性重生成（逐字节一致）
  P4  欢迎窗品牌面：上游 SVG 已删除，改为标志位图 + 真实文字字标
  P5  安装器 UI 文案零上游品牌名（`installer/strings.nsh`）
  P6  上游品牌素材零引用（合成夹具 `scripts/clean.spec.ts` 除外）
  P7  行为：`apps/desktop/tests/welcome-renderer.client.spec.tsx` 全绿（快照不变）
  P8  回归：上游桌面壳套件全绿（`--no-suite` 可跳过）
P9  上游差异集条目数 = 120（差异集 12 的 106 + 13 新增 13 + 14 新增 1；2026-10-12 基线迁移后差异集 07 增补 project-manager.spec.ts）
  P10 补丁可逆重放（`git apply --reverse --check`）

用法：python scripts/verify_diffset13_login_installer_brand.py [--no-suite]
退出码：全部通过为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import argparse
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
PATCH = REPO / "patches" / "diffset-13-login-installer-brand.patch"
GENERATOR = REPO / "scripts" / "make_brand_assets.ps1"

INSTALLER_ASSETS = "apps/desktop/installer/assets"
RENDERER_ASSETS = "apps/desktop/renderer/assets"
WELCOME_PAGE = "apps/desktop/src/client/WelcomePage.tsx"
WELCOME_CSS = "apps/desktop/renderer/welcome.css"
INSTALLER_STRINGS = "apps/desktop/installer/strings.nsh"
WELCOME_SPEC = "apps/desktop/tests/welcome-renderer.client.spec.tsx"

# 素材：文件 → (宽, 高, 是否不透明)
ASSETS = {
    f"{INSTALLER_ASSETS}/brand.png": (600, 196, False),
    f"{INSTALLER_ASSETS}/brand-2x.png": (1200, 392, False),
    f"{INSTALLER_ASSETS}/brand-dark.png": (600, 196, False),
    f"{INSTALLER_ASSETS}/brand-dark-2x.png": (1200, 392, False),
    f"{INSTALLER_ASSETS}/uninstaller-sidebar.png": (164, 314, True),
    f"{RENDERER_ASSETS}/welcome-brand-mark.png": (80, 80, False),
}

EXPECTED_FILES = sorted([
    *ASSETS.keys(),
    f"{RENDERER_ASSETS}/welcome-brand.svg",          # 删除
    WELCOME_PAGE,
    WELCOME_CSS,
    INSTALLER_STRINGS,
    WELCOME_SPEC,
    "apps/desktop/README.md",
    "apps/desktop/README.zh.md",
])

# 允许保留旧素材路径的合成夹具（自建输入与期望，不读真实素材）
ALLOWED_SVG_REFERENCES = {"scripts/clean.spec.ts"}
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


def png_size(path: Path) -> tuple[int, int, bool]:
    """Read a PNG's IHDR: width, height and whether it looks like an RGB (opaque) file."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name} is not a PNG")
    width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    color_type = data[25]
    return width, height, color_type in (2, 3)  # truecolor / indexed ⇒ no alpha channel


def regenerate() -> Path:
    """Run the asset generator into an isolated directory and return its root."""
    out = Path(tempfile.mkdtemp(prefix=".d13-assets-", dir=str(REPO)))
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(GENERATOR), "-Out", str(out)],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"generator failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-suite", action="store_true", help="跳过上游客户端套件回归")
    args = parser.parse_args()

    print("=" * 60)
    print("差异集 13 门禁：登录界面与安装界面的品牌面")
    print("=" * 60)

    # ── P1 补丁枚举 ──
    text = PATCH.read_text(encoding="utf-8", errors="replace") if PATCH.exists() else ""
    files = sorted({m.group(1) for m in re.finditer(r"^diff --git a/(.+?) b/", text, re.MULTILINE)})
    record(bool(text) and files == EXPECTED_FILES,
           f"P1 差异集 13 权威枚举 = {len(files)} 文件（期望 {len(EXPECTED_FILES)}）")

    # ── P2 素材存在且几何一致 ──
    geometry_ok, details = True, []
    for rel, (width, height, opaque) in ASSETS.items():
        path = UPSTREAM / rel
        if not path.exists():
            geometry_ok = False
            details.append(f"{rel}: 缺失")
            continue
        got_w, got_h, got_opaque = png_size(path)
        if (got_w, got_h) != (width, height) or got_opaque != opaque:
            geometry_ok = False
            details.append(f"{rel}: {got_w}x{got_h} opaque={got_opaque}")
    record(geometry_ok, f"P2 六个品牌素材尺寸/通道一致（偏差: {details or '无'}）")

    # ── P3 确定性重生成 ──
    out = regenerate()
    try:
        drift = []
        for rel in ASSETS:
            generated = out / rel
            current = UPSTREAM / rel
            if not generated.exists() or generated.read_bytes() != current.read_bytes():
                drift.append(rel)
        record(not drift, f"P3 素材可由生成器确定性重生成（漂移: {drift or '无'}）")
    finally:
        shutil.rmtree(out, ignore_errors=True)

    # ── P4 欢迎窗品牌面 ──
    welcome_page = read(WELCOME_PAGE)
    welcome_css = read(WELCOME_CSS)
    record(not (UPSTREAM / f"{RENDERER_ASSETS}/welcome-brand.svg").exists(),
           "P4 上游字标 SVG 已删除（welcome-brand.svg 不存在）")
    record('src="assets/welcome-brand-mark.png"' in welcome_page
           and 'className="brandName"' in welcome_page
           and "{m.welcomeBrand}" in welcome_page,
           "P4 WelcomePage 改为标志位图 + 本地化产品名字标")
    record(".brandMark" in welcome_css and ".brandName" in welcome_css
           and "var(--dsw-font-family-brand)" in welcome_css,
           "P4 字标排版走窗口品牌字体变量（随主题取色，无需第二张位图）")

    # ── P5 安装器文案 ──
    strings = read(INSTALLER_STRINGS)
    record("DeepSeek" not in strings and "WorkNexus-DSH" in strings,
           "P5 安装器 UI 文案无上游品牌名（启动/占用/安装目录三条）")

    # ── P6 旧素材零引用 ──
    hits = subprocess.run(["rg", "-l", "welcome-brand.svg", "--glob", "!**/node_modules/**",
                           "--glob", "!**/.desktop-build/**", "--glob", "!**/lib/**", "."],
                          cwd=str(UPSTREAM), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.splitlines()
    normalized = {line.strip().replace("\\", "/").lstrip("./") for line in hits if line.strip()}
    unexpected = sorted(normalized
                        - ALLOWED_SVG_REFERENCES - {".git"})
    record(not unexpected, f"P6 旧素材仅存于登记夹具（其余引用: {unexpected or '无'}）")

    # ── P7 欢迎窗用例 ──
    vitest = UPSTREAM / "node_modules" / ".bin" / ("vitest.CMD" if sys.platform == "win32" else "vitest")
    if not vitest.exists():
        record(False, f"P7 找不到上游 vitest：{vitest}")
    else:
        run = subprocess.run([str(vitest), "run", "apps/desktop/tests/welcome-renderer.client.spec.tsx"],
                             cwd=str(UPSTREAM), capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        out_text = run.stdout + run.stderr
        record(run.returncode == 0 and " failed" not in out_text,
               "P7 欢迎窗用例全绿（标志位图 + 本地化字标 + 快照不变）")

    # ── P8 桌面壳套件回归 ──
    if args.no_suite:
        print("[跳过] P8 上游桌面壳套件（--no-suite）")
    elif not vitest.exists():
        record(False, f"P8 找不到上游 vitest：{vitest}")
    else:
        run = subprocess.run([str(vitest), "run", "--project", "thread-safe", "apps/desktop/tests"],
                             cwd=str(UPSTREAM), capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        tail = (run.stdout + run.stderr).splitlines()[-6:]
        record(run.returncode == 0, f"P8 上游桌面壳套件全绿 :: {' / '.join(line.strip() for line in tail if line.strip())}")

    # ── P9 差异集条目数 ──
    paths = changed_paths()
    record(len(paths) == EXPECTED_DIFFSET_PATHS,
           f"P9 上游差异集条目数 = {len(paths)}（差异集 12 的 105 + 13 新增 13 + 14 新增 1）")
    record(all(path in paths for path in EXPECTED_FILES),
           "P9 差异集 13 的 13 个文件都在改动集内")

    # ── P10 补丁可逆重放 ──
    check = git("apply", "--reverse", "--check", "--binary", str(PATCH))
    record(check.returncode == 0,
           f"P10 差异集 13 补丁可逆重放：{check.stderr.strip() or 'ok'}")

    failures = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failures)} [OK] / {len(failures)} [FAIL]")
    for detail in failures:
        print(f"  - {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
