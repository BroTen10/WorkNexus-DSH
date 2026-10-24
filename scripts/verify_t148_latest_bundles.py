#!/usr/bin/env python
"""T-148 门禁：插件市场与五个随包根组件处于目标最新版。

断言：
  A1 锁文件中的 5 个根包版本与 T-148 目标一致
  A2 桌面运行时树中的 5 个根包版本一致
  A3 第三方声明包含新版本且不再含旧版本
  A4 包集为 88 个 tgz = 5 个根 + 83 个依赖闭包
  A5 旧版 tgz / 许可证未被继续携带

用法：
  python scripts/verify_t148_latest_bundles.py
  python scripts/verify_t148_latest_bundles.py --check-npm
"""

from __future__ import annotations

import argparse
import json
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
EXPECTED = {
    "dshmarket": "1.66.45",
    "dsh-claude-style": "0.18.1",
    "dsh-better-sidebar": "0.28.0",
    "@tt-a1i/archify-dsh": "1.0.0",
    "@linxin666/dsh-client-ui-skill-explorer": "0.4.8",
}
OLD = {
    "dshmarket": "1.66.42",
    "dsh-claude-style": "0.16.3",
}
RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def package_version(directory: Path) -> str | None:
    try:
        return json.loads((directory / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-npm", action="store_true", help="同时向 npm registry 核对 dist-tags.latest")
    args = parser.parse_args()
    print("=" * 60)
    print("T-148 门禁：插件市场与预置插件最新版")
    print("=" * 60)

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    locked = {item["name"]: item["version"] for item in lock["packages"] if item.get("name") in EXPECTED}
    record(locked == EXPECTED, f"A1 锁文件根版本 = {locked}（期望 {EXPECTED}）")

    runtime = {name: package_version(RUNTIME / name) for name in EXPECTED}
    record(runtime == EXPECTED, f"A2 运行时根版本 = {runtime}（期望 {EXPECTED}）")

    notices = NOTICES.read_text(encoding="utf-8") if NOTICES.is_file() else ""
    notice_ok = all(f"`{name}` | {version} |" in notices for name, version in EXPECTED.items())
    old_notice = any(f"`{name}` | {version} |" in notices for name, version in OLD.items())
    record(notice_ok and not old_notice, f"A3 第三方声明包含新版本且无旧版本（new={notice_ok} old={old_notice}）")

    produced = {path.name for path in PACKED.glob("*.tgz")}
    root_files = {item["file"] for item in lock["packages"] if item.get("name") in EXPECTED}
    expected_files = {item["file"] for item in lock["packages"] if "file" in item}
    record(len(produced) == 88 and len(root_files) == 5 and produced == expected_files,
           f"A4 包集 88 = 5 根 + 83 闭包（actual={len(produced)} roots={len(root_files)} exact={produced == expected_files}）")

    old_files = [
        f"dshmarket-{OLD['dshmarket']}.tgz",
        f"dsh-claude-style-{OLD['dsh-claude-style']}.tgz",
        f"dshmarket-{OLD['dshmarket']}.LICENSE.txt",
        f"dsh-claude-style-{OLD['dsh-claude-style']}.LICENSE.txt",
    ]
    residues = [name for name in old_files if (PACKED / name).exists() or (LICENSES / name).exists()]
    record(not residues, f"A5 旧版 tgz / 许可证未残留（{residues or '无'}）")

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
