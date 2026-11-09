#!/usr/bin/env python
"""T-148 / T-150 / T-151 门禁：随包插件市场处于目标最新版。

断言：
  A1 锁文件中的唯一根包 dshmarket 与目标版本一致
  A2 桌面运行时树中的 dshmarket 版本一致
  A3 第三方声明包含新版本且不再含旧版本
  A4 包集精确等于锁文件 = 1 个根 + 运行依赖闭包
  A5 旧版及四个退役预置的 tgz / 许可证未被继续携带

用法：
  python scripts/verify_t148_latest_bundles.py
  python scripts/verify_t148_latest_bundles.py --check-npm
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
RUNTIME = REPO / "repos" / "deepseek-harness" / "apps" / "desktop" / ".desktop-build" / "targets" / "win-x64" / "dsh" / "node_modules"
LOCK = REPO / "configs" / "vendor" / "third-party-bundles.lock.json"
PACKED = REPO / ".worknexus-packed"
LICENSES = REPO / "configs" / "vendor" / "licenses"
NOTICES = REPO / "repos" / "deepseek-harness" / "WORKNEXUS-THIRD-PARTY-NOTICES.md"
INSTALLED_ASAR = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "WorkNexus-DSH" / "resources" / "app.asar"
EXPECTED = {"dshmarket": "1.73.14"}
OLD = {"dshmarket": "1.73.7"}
RETIRED = (
    "dsh-claude-style",
    "dsh-better-sidebar",
    "tt-a1i-archify-dsh",
    "linxin666-dsh-client-ui-skill-explorer",
)
RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def package_version(directory: Path) -> str | None:
    try:
        return json.loads((directory / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def asar_entries(path: Path) -> dict[str, tuple[int, int]]:
    raw = path.read_bytes()
    header_size = struct.unpack("<I", raw[4:8])[0]
    json_size = struct.unpack("<I", raw[12:16])[0]
    header = json.loads(raw[16:16 + json_size].decode("utf-8"))
    base = 8 + header_size
    entries: dict[str, tuple[int, int]] = {}

    def walk(node: dict, prefix: str) -> None:
        for name, metadata in (node.get("files") or {}).items():
            relative = f"{prefix}/{name}" if prefix else name
            if "files" in metadata:
                walk(metadata, relative)
            elif "size" in metadata:
                entries[relative] = (base + int(metadata.get("offset", "0")), int(metadata["size"]))

    walk(header, "")
    return entries


def installed_versions() -> dict[str, str | None]:
    if not INSTALLED_ASAR.is_file():
        return {}
    raw = INSTALLED_ASAR.read_bytes()
    entries = asar_entries(INSTALLED_ASAR)
    versions: dict[str, str | None] = {}
    for name in EXPECTED:
        rel = f"dsh/node_modules/{name}/package.json"
        if rel not in entries:
            versions[name] = None
            continue
        offset, size = entries[rel]
        versions[name] = json.loads(raw[offset:offset + size].decode("utf-8")).get("version")
    return versions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-npm", action="store_true", help="同时向 npm registry 核对 dist-tags.latest")
    args = parser.parse_args()
    print("=" * 60)
    print("T-148 / T-150 / T-151 门禁：随包插件市场最新版")
    print("=" * 60)

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    locked = {item["name"]: item["version"] for item in lock["packages"] if item.get("name") in EXPECTED}
    record(locked == EXPECTED, f"A1 锁文件根版本 = {locked}（期望 {EXPECTED}）")

    runtime = {name: package_version(RUNTIME / name) for name in EXPECTED}
    record(runtime == EXPECTED, f"A2 运行时根版本 = {runtime}（期望 {EXPECTED}）")

    installed = installed_versions()
    record(installed == EXPECTED, f"A2b 安装态 app.asar 根版本 = {installed}（期望 {EXPECTED}）")

    notices = NOTICES.read_text(encoding="utf-8") if NOTICES.is_file() else ""
    notice_ok = all(f"`{name}` | {version} |" in notices for name, version in EXPECTED.items())
    old_notice = any(f"`{name}` | {version} |" in notices for name, version in OLD.items())
    record(notice_ok and not old_notice, f"A3 第三方声明包含新版本且无旧版本（new={notice_ok} old={old_notice}）")

    produced = {path.name for path in PACKED.glob("*.tgz")}
    root_files = {item["file"] for item in lock["packages"] if item.get("name") in EXPECTED}
    expected_files = {item["file"] for item in lock["packages"] if "file" in item}
    record(len(root_files) == 1 and produced == expected_files,
           f"A4 包集精确等于锁文件 = 1 根 + 运行闭包（actual={len(produced)} "
           f"roots={len(root_files)} exact={produced == expected_files}）")

    old_files = [
        f"dshmarket-{OLD['dshmarket']}.tgz",
        f"dshmarket-{OLD['dshmarket']}.LICENSE.txt",
    ]
    residues = [name for name in old_files if (PACKED / name).exists() or (LICENSES / name).exists()]
    residues.extend(
        path.name
        for path in [*PACKED.glob("*.tgz"), *LICENSES.glob("*.LICENSE.txt")]
        if any(path.name.startswith(name) for name in RETIRED)
    )
    record(not residues, f"A5 旧版/退役 tgz 与许可证未残留（{residues or '无'}）")

    if args.check_npm:
        mismatches = []
        for name, expected in EXPECTED.items():
            url = f"https://registry.npmjs.org/{name.replace('/', '%2f')}"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "worknexus-dsh-t148"}), timeout=30) as response:
                    latest = json.loads(response.read().decode("utf-8"))["dist-tags"]["latest"]
                if latest != expected:
                    mismatches.append(f"{name}: npm={latest} expected={expected}")
            except Exception as error:  # gate reports the lookup failure instead of pretending success
                mismatches.append(f"{name}: {error}")
        record(not mismatches, f"A6 npm latest 对照（{mismatches or '全部一致'}）")

    failed = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failed)} [OK] / {len(failed)} [FAIL]")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
