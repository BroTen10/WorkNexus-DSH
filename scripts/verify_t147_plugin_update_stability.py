#!/usr/bin/env python
"""T-147 门禁：任意插件更新不得卸载正在服务的插件市场。

根因：T-143 把 `dshmarket` 物化进 profile 的 `node_modules`，但没有登记为
profile 依赖。pnpm 在任意 remove/add 中把它当作 extraneous 移到 `.ignored`：

  [WARN] Moving dshmarket to "node_modules\\.ignored\\dshmarket_N"

此时 `dsh-market` 正在处理更新请求，却因包目录消失进入 UNLOADING，后续 add
永远没有机会执行。修复是让市场运行在 `<DSH_HOME>/dshmarket`，由 profile 用户层
用显式相对路径 `../../dshmarket/lib/index.js` 挂载；依赖闭包放在市场自己的
`node_modules` 下。

断言：
  S1 市场使用显式路径，且物化目标位于 profile 之外
  S2 旧 profile 的裸包名行迁移到显式路径，旧 profile 内市场副本被移除
  S3 市场及其依赖闭包在新位置幂等物化
  P1 真实 pnpm 对照：profile 内未声明市场会被移到 `.ignored`
  P2 真实 pnpm 对照：profile 外市场在插件 remove 后字节不变

用法：python scripts/verify_t147_plugin_update_stability.py
退出码：全部 [OK] 为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
DESKTOP = UPSTREAM / "apps" / "desktop"
BACKFILL = DESKTOP / "src" / "profile-bundle-backfill.ts"
NODE = shutil.which("node") or "node"
PNPM = UPSTREAM / "node_modules" / "pnpm" / "bin" / "pnpm.cjs"
RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tree_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def run(command: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def check_static() -> None:
    text = BACKFILL.read_text(encoding="utf-8")
    explicit = "WORKNEXUS_MARKET_ENTRY = '../../dshmarket/lib/index.js'" in text
    outside = "const homeDir = dirname(dirname(profileDir))" in text
    nested_closure = "join(homeDir, WORKNEXUS_MARKET_PLUGIN, 'node_modules')" in text
    legacy_cleanup = "const legacyMarket = join(profileModules, WORKNEXUS_MARKET_PLUGIN)" in text
    record(explicit and outside and nested_closure and legacy_cleanup,
           f"S1 市场在 profile 外使用显式路径并清理旧副本（explicit={explicit} outside={outside} "
           f"closure={nested_closure} cleanup={legacy_cleanup}）")


def materialization_probe() -> None:
    root = Path(tempfile.mkdtemp(prefix="wn-t147-materialize-"))
    try:
        profile = root / "profiles" / "desktop"
        runtime = root / "runtime"
        profile.mkdir(parents=True)
        write_json(profile / "package.json", {
            "name": "dsh-profile-desktop",
            "private": True,
            "dependencies": {},
            "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base"]}},
        })
        legacy_patch = "\n".join([
            "- insert:",
            "    - id: dsh-market",
            "      name: 'dshmarket'",
            "",
        ])
        (profile / "cordis.patch.yml").write_text(legacy_patch, encoding="utf-8")
        write_json(profile / "node_modules" / "dshmarket" / "package.json", {
            "name": "dshmarket",
            "version": "1.66.45",
        })
        write_json(root / "dshmarket" / "package.json", {
            "name": "dshmarket",
            "version": "1.66.44",
        })
        (root / "dshmarket" / "stale.js").write_text("stale\n", encoding="utf-8")

        packages = {
            "dshmarket": {
                "name": "dshmarket",
                "version": "1.66.45",
                "dependencies": {"js-yaml": "^4.3.2", "undici": "^7.29.1"},
                "peerDependencies": {"@deepseek-ai/schemastery": "^3.18.1"},
            },
            "js-yaml": {
                "name": "js-yaml",
                "version": "4.3.2",
                "dependencies": {"argparse": "^2.0.1"},
            },
            "argparse": {"name": "argparse", "version": "2.0.1"},
            "undici": {"name": "undici", "version": "7.29.1"},
            "@deepseek-ai/schemastery": {
                "name": "@deepseek-ai/schemastery",
                "version": "3.18.5",
            },
            "@deepseek-ai/cordis-plugin-include": {
                "name": "@deepseek-ai/cordis-plugin-include",
                "version": "1.0.10",
                "dependencies": {"@deepseek-ai/cordis": "4.0.5"},
            },
            "@deepseek-ai/cordis": {"name": "@deepseek-ai/cordis", "version": "4.0.5"},
        }
        for name, manifest in packages.items():
            package = runtime / "node_modules" / name
            write_json(package / "package.json", manifest)
            if name == "dshmarket":
                (package / "lib").mkdir(parents=True)
                (package / "lib" / "index.js").write_text("export const name = 'dsh-market'\n", encoding="utf-8")

        script = root / "probe.mjs"
        source = BACKFILL.as_uri()
        script.write_text(
            "import { backfillProfileMarketPlugin, materializePresetPlugins } from "
            + json.dumps(source)
            + "\n"
            + "const profile = process.argv[2]\n"
            + "const runtime = process.argv[3]\n"
            + "const firstPatch = backfillProfileMarketPlugin(profile)\n"
            + "const secondPatch = backfillProfileMarketPlugin(profile)\n"
            + "const first = materializePresetPlugins(profile, runtime)\n"
            + "const second = materializePresetPlugins(profile, runtime)\n"
            + "console.log(JSON.stringify({ firstPatch, secondPatch, first, second }))\n",
            encoding="utf-8",
        )
        proc = run(
            [NODE, "--import", "tsx/esm", str(script), str(profile), str(runtime)],
            UPSTREAM,
        )
        if proc.returncode != 0:
            record(False, f"S2/S3 物化探针退出 {proc.returncode}: {(proc.stderr or proc.stdout)[-600:]}")
            return
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        patch = (profile / "cordis.patch.yml").read_text(encoding="utf-8")
        market = root / "dshmarket"
        market_version = json.loads((market / "package.json").read_text(encoding="utf-8"))["version"]
        required = [
            market / "package.json",
            market / "lib" / "index.js",
            market / "node_modules" / "js-yaml" / "package.json",
            market / "node_modules" / "argparse" / "package.json",
            market / "node_modules" / "undici" / "package.json",
            market / "node_modules" / "@deepseek-ai" / "schemastery" / "package.json",
            market / "node_modules" / "@deepseek-ai" / "cordis-plugin-include" / "package.json",
            market / "node_modules" / "@deepseek-ai" / "cordis" / "package.json",
        ]
        migrated = result["firstPatch"] is True and result["secondPatch"] is False
        explicit = "name: '../../dshmarket/lib/index.js'" in patch and "name: 'dshmarket'" not in patch
        old_gone = not (profile / "node_modules" / "dshmarket").exists()
        materialized = all(path.is_file() for path in required)
        idempotent = result["second"]["copied"] == []
        record(migrated and explicit and old_gone,
               f"S2 旧裸包名迁移且 profile 内旧副本移除（write={result['firstPatch']} "
               f"second={result['secondPatch']} explicit={explicit} old_gone={old_gone}）")
        record(materialized and idempotent and market_version == "1.66.45",
               f"S3 市场与依赖闭包在 profile 外幂等物化（files={[path.is_file() for path in required]} "
               f"version={market_version} second_copied={result['second']['copied']}）")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def pnpm_probe() -> None:
    root = Path(tempfile.mkdtemp(prefix="wn-t147-pnpm-"))
    try:
        plugin = root / "probe-plugin"
        write_json(plugin / "package.json", {
            "name": "probe-plugin",
            "version": "1.0.0",
            "main": "index.js",
        })
        (plugin / "index.js").write_text("module.exports = 1\n", encoding="utf-8")

        old_profile = root / "old-profile"
        new_profile = root / "new-profile"
        for profile in (old_profile, new_profile):
            profile.mkdir(parents=True)
            (profile / "pnpm-workspace.yaml").write_text(
                "packages:\n  - .\n\nnodeLinker: hoisted\nautoInstallPeers: false\n",
                encoding="utf-8",
            )
            write_json(profile / "package.json", {
                "name": profile.name,
                "private": True,
                "dependencies": {"probe-plugin": "file:../probe-plugin"},
            })
            installed = run([NODE, str(PNPM), "install", "--config.ignore-scripts=true"], profile)
            if installed.returncode != 0:
                record(False, f"P0 pnpm 初始安装失败: {(installed.stderr or installed.stdout)[-600:]}")
                return

        old_market = old_profile / "node_modules" / "dshmarket"
        write_json(old_market / "package.json", {"name": "dshmarket", "version": "1.66.45"})
        external_market = root / "dshmarket"
        write_json(external_market / "package.json", {"name": "dshmarket", "version": "1.66.45"})
        (external_market / "stable.js").write_text("export default 1\n", encoding="utf-8")
        before = tree_hash(external_market)

        for profile in (old_profile, new_profile):
            removed = run([NODE, str(PNPM), "remove", "probe-plugin", "--config.ignore-scripts=true"], profile)
            if removed.returncode != 0:
                record(False, f"P1 pnpm remove 失败: {(removed.stderr or removed.stdout)[-600:]}")
                return

        ignored = old_profile / "node_modules" / ".ignored"
        old_moved = not old_market.exists() and any(
            child.name == "dshmarket" or child.name.startswith("dshmarket_")
            for child in ignored.iterdir()
        ) if ignored.is_dir() else False
        record(old_moved, f"P1 对照：profile 内未声明市场被 pnpm 移到 .ignored（moved={old_moved}）")

        after = tree_hash(external_market)
        external_stable = external_market.is_dir() and before == after
        record(external_stable and not (new_profile / "node_modules" / "dshmarket").exists(),
               f"P2 对照：profile 外市场经过插件 remove 后字节不变（sha256={after[:16]}…）")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    print("=" * 64)
    print("T-147 门禁：任意插件更新不得卸载正在服务的插件市场")
    print("=" * 64)
    if not PNPM.is_file():
        record(False, f"缺少 pnpm：{PNPM}")
    else:
        check_static()
        materialization_probe()
        pnpm_probe()
    failed = [detail for ok, detail in RESULTS if not ok]
    print("-" * 64)
    print(f"结果: {len(RESULTS) - len(failed)} [OK] / {len(failed)} [FAIL]")
    for detail in failed:
        print(f"  - {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
