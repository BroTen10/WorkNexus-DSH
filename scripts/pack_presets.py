#!/usr/bin/env python
"""个人版预置包集：取回 `dshmarket` + 三个预置插件及其运行闭包。

与旧 `pack_enterprise.py` 的区别：
  - 不再打包 `packages/*`、`bundles/*`、`plugins/*`（企业层已迁至 WorkNexus-Enterprise）；
  - 只按 `configs/vendor/third-party-bundles.lock.json` 取回第三方 tgz；
  - 产物目录仍为 `.worknexus-packed`，供 `prepare-package-set.ts` 的
    `PERSONAL_PRESET_ROOTS` 使用。

用法：
  python scripts/pack_presets.py
  python scripts/pack_presets.py --out .worknexus-packed
  python scripts/pack_presets.py --verify-only
退出码：全部就绪为 0；任一缺失/不匹配为 1。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "configs" / "vendor" / "third-party-bundles.lock.json"
FETCHER = REPO / "scripts" / "fetch_third_party_bundles.py"
ROOT_NAMES = (
    "dshmarket",
    "dsh-better-sidebar",
    "dsh-claude-style",
    "@linxin666/dsh-client-ui-skill-explorer",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="取回个人版预置第三方 bundle")
    parser.add_argument("--out", default=".worknexus-packed")
    parser.add_argument("--verify-only", action="store_true", help="只校验，不下载/不改目录")
    parser.add_argument("--clean", action="store_true", help="先清空包集目录再取回（默认保留已有 tgz，幂等重试）")
    args = parser.parse_args()

    if not LOCK.is_file():
        print(f"[FAIL] 锁文件缺失：{LOCK}")
        return 1
    if not FETCHER.is_file():
        print(f"[FAIL] 取回脚本缺失：{FETCHER}")
        return 1

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    packages = lock.get("packages", [])
    expected = {item["file"]: item["name"] for item in packages if "file" in item and "name" in item}
    out = (REPO / args.out).resolve()

    if not args.verify_only:
        out.mkdir(parents=True, exist_ok=True)
        if args.clean:
            for stale in out.glob("*.tgz"):
                stale.unlink()

    command = [sys.executable, str(FETCHER), "--out", str(out)]
    if args.verify_only:
        command.append("--verify-only")
    proc = subprocess.run(command, cwd=str(REPO), check=False)
    if proc.returncode != 0:
        print("[FAIL] 第三方 bundle 取回/校验失败（见上方 fetch 输出）")
        return 1

    produced = {path.name for path in out.glob("*.tgz")}
    missing = sorted(set(expected) - produced)
    extra = sorted(produced - set(expected))
    enterprise = sorted(name for name in produced if name.startswith("worknexus-"))
    root_files = {item["file"] for item in packages if item.get("name") in ROOT_NAMES}

    print("-" * 60)
    print(f"个人预置包集: {out}")
    print(f"tarball 数: {len(produced)}（锁文件期望 {len(expected)}）")
    failures: list[str] = []
    if missing:
        failures.append(f"缺少 {len(missing)} 个 tgz：{', '.join(missing[:5])}")
    if extra:
        failures.append(f"多出 {len(extra)} 个未登记 tgz：{', '.join(extra[:5])}")
    if enterprise:
        failures.append(f"仍含企业包 tgz：{', '.join(enterprise[:5])}")
    if not root_files.issubset(produced):
        failures.append(f"缺少预置根 tgz：{', '.join(sorted(root_files - produced))}")
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        print(f"结果: 0 [OK] / {len(failures)} [FAIL]")
        return 1
    print(f"[OK] 4 个预置根 + 运行闭包齐全；无 @worknexus 企业包")
    print(f"结果: {len(produced)} [OK] / 0 [FAIL]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
