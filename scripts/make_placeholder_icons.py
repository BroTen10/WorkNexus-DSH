#!/usr/bin/env python
"""生成 WorkNexus-DSH 的**占位**图标（T-021 裁决：品牌素材缺失时用临时占位）。

为什么自己生成：本机没有 Pillow，也没有企业品牌素材（T-008 C-1）。
本脚本只用标准库（zlib/struct）写出确定性的 PNG 与 PNG-in-ICO，
保证「可复现、可审计、可整体替换」——正式素材到位后整目录替换即可。

产物（写入 `--resources` 指向的桌面端 resources 目录）：
  icon.png          512×512   （通用/安装包）
  icon-windows.png  256×256   （Windows）
  icon-macos.png    512×512   （macOS）
  tray-windows.ico  7 档位图   （托盘，PNG-in-ICO：16/20/24/32/40/48/64）
  icon.svg / icon-windows.svg / icon-macos.svg   （矢量占位，与 PNG 同构图）

托盘图标为什么是多档：上游 `apps/desktop/tests/tray-icon.spec.ts` 要求提交的 ICO 覆盖
上游 `render-tray-icon.ts` 的 `TRAY_ICON_SIZES = [16, 20, 24, 32, 40, 48, 64]`（Windows 按显示
缩放挑最合适的一档，避免放大发虚）。本脚本按同一尺寸集逐档栅格化后打包成多图像 ICO —— 只改
「有几档」，不改任何一档的画法。矢量占位同时带上上游约定的 `<g id="tray-glyph">` 标记
（`renderTrayIconEntries()` 以此定位托盘前景），因此上游 `pnpm --filter @deepseek-ai/dsh-desktop
run render:tray-icon` 也是可用路径；两条路径只需在提交前跑其中一条。

用法：
  python scripts/make_placeholder_icons.py                 # 写入上游 resources
  python scripts/make_placeholder_icons.py --out <目录>     # 写到别处
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
DEFAULT_RESOURCES = REPO / "repos" / "deepseek-harness" / "apps" / "desktop" / "resources"

BG = (31, 58, 138)      # #1F3A8A  WorkNexus 占位主色
FG = (255, 255, 255)

# "W" 的四段折线（归一化坐标 0..1）
STROKES = [
    ((0.19, 0.31), (0.34, 0.69)),
    ((0.34, 0.69), (0.50, 0.44)),
    ((0.50, 0.44), (0.66, 0.69)),
    ((0.66, 0.69), (0.81, 0.31)),
]
STROKE_W = 0.065  # 归一化笔画粗细


def _dist_to_segment(px: float, py: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def render(size: int) -> list[bytes]:
    """返回 PNG 所需的逐行 RGB 字节。"""
    rows: list[bytes] = []
    for y in range(size):
        row = bytearray()
        py = (y + 0.5) / size
        for x in range(size):
            px = (x + 0.5) / size
            on = any(_dist_to_segment(px, py, a, b) <= STROKE_W / 2 for a, b in STROKES)
            r, g, b = FG if on else BG
            row += bytes((r, g, b))
        rows.append(bytes(row))
    return rows


def write_png(path: Path, size: int) -> None:
    rows = render(size)
    raw = b"".join(b"\x00" + r for r in rows)  # 每行 filter type 0

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8bit truecolor
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


# 与上游 `apps/desktop/scripts/render-tray-icon.ts` 的 TRAY_ICON_SIZES 保持一致（升序）
TRAY_SIZES = (16, 20, 24, 32, 40, 48, 64)


def write_ico(path: Path, sizes: tuple[int, ...] = TRAY_SIZES) -> None:
    """PNG-in-ICO（每档一个图像条目；Vista 之后直接读 PNG 载荷）。"""
    bitmaps: list[tuple[int, bytes]] = []
    for size in sizes:
        tmp = path.with_suffix(f".tmp{size}.png")
        write_png(tmp, size)
        bitmaps.append((size, tmp.read_bytes()))
        tmp.unlink()

    header = struct.pack("<HHH", 0, 1, len(bitmaps))
    entries = bytearray()
    offset = len(header) + 16 * len(bitmaps)
    for size, png in bitmaps:
        # 256 及以上在单字节字段里写 0
        edge = size if size < 256 else 0
        entries += struct.pack("<BBBBHHII", edge, edge, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    path.write_bytes(header + bytes(entries) + b"".join(png for _, png in bitmaps))


def svg(size: int = 1024) -> str:
    """矢量占位；坐标系用上游托盘渲染器约定的 1024 方。"""
    poly = " ".join(
        f"{a[0] * size:.1f},{a[1] * size:.1f} {b[0] * size:.1f},{b[1] * size:.1f}"
        for a, b in STROKES
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" role="img" aria-label="WorkNexus-DSH placeholder icon">\n'
        f'  <rect width="{size}" height="{size}" fill="#1F3A8A"/>\n'
        f'  <g id="tray-glyph" stroke="#FFFFFF" stroke-width="{STROKE_W * size:.1f}" '
        f'stroke-linecap="round" stroke-linejoin="round" fill="none">\n'
        f"    {poly}\n"
        f"  </g>\n"
        f"</svg>\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_RESOURCES))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    write_png(out / "icon.png", 512)
    write_png(out / "icon-windows.png", 256)
    write_png(out / "icon-macos.png", 512)
    write_ico(out / "tray-windows.ico", TRAY_SIZES)
    body = svg(1024)
    for name in ("icon.svg", "icon-windows.svg", "icon-macos.svg"):
        # 固定 LF：差异集补丁是逐字节输入，行尾随平台漂移会在 rebase 时产生假冲突
        (out / name).write_text(body, encoding="utf-8", newline="\n")

    for name in ("icon.png", "icon-windows.png", "icon-macos.png", "tray-windows.ico",
                 "icon.svg", "icon-windows.svg", "icon-macos.svg"):
        p = out / name
        print(f"[OK] {name:20s} {p.stat().st_size:>8d} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
