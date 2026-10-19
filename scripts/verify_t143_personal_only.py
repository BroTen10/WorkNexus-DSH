#!/usr/bin/env python
"""T-143 门禁：个人版宿主清理。

断言：
  P1  企业目录不存在（bundles/plugins/packages/services）
  P2  prepare-package-set.ts 无 @worknexus 根；默认 roots = dshmarket + 三预置
  P3  project-manager.ts profile bundles 无 @worknexus；只含三预置
  P4  profile-bundle-backfill.ts 清理 @worknexus/* + 回填预置；行为探针通过
  P5  .worknexus-packed 无企业 tgz；4 个预置根 + 86 闭包齐全
  P6  package_desktop_win_unsigned.py --dry-run 退出 0
  P7  隔离 profile 清理后无 @worknexus/*，备份存在且幂等
  P9  企业仓干净；本仓无企业目录 tracked 文件

用法：python scripts/verify_t143_personal_only.py
退出码：全部 [OK] 为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import json
import os
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
PACKED = REPO / ".worknexus-packed"
LOCK = REPO / "configs" / "vendor" / "third-party-bundles.lock.json"
ENTERPRISE_REPO = REPO.parent / "WorkNexus-Enterprise"
NODE = shutil.which("node") or "node"


def find_git() -> str:
    found = shutil.which("git")
    if found:
        return found
    github_desktop = Path(os.environ.get("LOCALAPPDATA", "")) / "GitHubDesktop"
    candidates = sorted(
        github_desktop.glob("app-*/resources/app/git/cmd/git.exe"),
        reverse=True,
    )
    return str(candidates[0]) if candidates else "git"


GIT = find_git()

RESULTS: list[tuple[str, bool, str]] = []


def record(criterion: str, ok: bool, detail: str) -> None:
    RESULTS.append((criterion, ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {criterion} {detail}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_p1() -> None:
    leftovers = [name for name in ("bundles", "plugins", "packages", "services") if (REPO / name).exists()]
    record("P1 企业目录已删除", not leftovers, f"残留={leftovers or '无'}")


def check_p2() -> None:
    text = read(DESKTOP / "scripts" / "prepare-package-set.ts")
    has_enterprise = "@worknexus/" in text
    has_market = "'dshmarket'" in text
    has_three = all(name in text for name in ("dsh-better-sidebar", "dsh-claude-style", "@linxin666/dsh-client-ui-skill-explorer"))
    record("P2 包集根无企业包", not has_enterprise and has_market and has_three,
           f"@worknexus={has_enterprise} dshmarket={has_market} 三预置={has_three}")


def check_p3() -> None:
    text = read(DESKTOP / "src" / "project-manager.ts")
    enterprise_names = (
        "@worknexus/ent-core",
        "@worknexus/plugin-enterprise-admin",
        "@worknexus/plugin-knowledge",
        "@worknexus/plugin-docgraph",
        "@worknexus/plugin-ipd",
        "@worknexus/plugin-acp",
        "@worknexus/plugin-market",
        "@worknexus/ent-client",
    )
    hits = [name for name in enterprise_names if name in text]
    has_three = all(name in text for name in ("dsh-better-sidebar", "dsh-claude-style", "@linxin666/dsh-client-ui-skill-explorer"))
    market_outside_bundles = "'dshmarket'" not in text
    record("P3 profile 初值无企业 bundle / 市场不入 bundle", not hits and has_three and market_outside_bundles,
           f"企业 bundle={hits or '无'} 三预置={has_three} dshmarket_not_in_bundles={market_outside_bundles}")


def check_p4_static() -> None:
    text = read(DESKTOP / "src" / "profile-bundle-backfill.ts")
    has_prefix = "STALE_ENTERPRISE_BUNDLE_PREFIX = '@worknexus/'" in text
    has_filter = "startsWith(STALE_ENTERPRISE_BUNDLE_PREFIX)" in text
    has_backup = ".bak-t143" in text
    has_market = (
        "WORKNEXUS_MARKET_PLUGIN = 'dshmarket'" in text
        and "WORKNEXUS_MARKET_ENTRY_ID = 'dsh-market'" in text
        and "backfillProfileMarketPlugin" in text
        and "'- insert:'" in text
    )
    has_closure = "materializeDependencyClosure" in text and "optionalDependencies" in text
    record("P4 清理逻辑、市场挂载与依赖闭包", has_prefix and has_filter and has_backup and has_market and has_closure,
           f"prefix={has_prefix} filter={has_filter} backup={has_backup} market={has_market} closure={has_closure}")


def check_p4_behavior() -> None:
    probe = Path(tempfile.mkdtemp(prefix="wn-t143-profile-"))
    try:
        original = {
            "name": "dsh-profile-desktop",
            "private": True,
            "dependencies": {
                "dsh-better-sidebar": "0.25.0",
                "dsh-claude-style": "0.13.2",
                "@linxin666/dsh-client-ui-skill-explorer": "0.4.6",
            },
            "dsh": {
                "profile": {
                    "bundles": [
                        "@deepseek-ai/dsh-base",
                        "@worknexus/ent-core",
                        "@worknexus/plugin-market",
                        "dsh-better-sidebar",
                        "custom-bundle",
                    ]
                }
            },
        }
        manifest = probe / "package.json"
        manifest.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        source = (DESKTOP / "src" / "profile-bundle-backfill.ts").as_uri()
        script = probe / "probe.mjs"
        script.write_text(
            "import { backfillProfileBundles } from " + json.dumps(source) + "\n"
            "const dir = process.argv[2]\n"
            "const first = backfillProfileBundles(dir)\n"
            "const second = backfillProfileBundles(dir)\n"
            "console.log(JSON.stringify({ first, second }))\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [NODE, "--import", "tsx/esm", str(script), str(probe)],
            cwd=str(UPSTREAM), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            record("P4 行为探针", False, f"exit={proc.returncode} {(proc.stderr or proc.stdout)[-400:]}")
            return
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        updated = json.loads(manifest.read_text(encoding="utf-8"))
        bundles = updated["dsh"]["profile"]["bundles"]
        no_enterprise = all(not name.startswith("@worknexus/") for name in bundles)
        presets = ["dsh-better-sidebar", "dsh-claude-style", "@linxin666/dsh-client-ui-skill-explorer"]
        has_presets = all(name in bundles for name in presets)
        order_ok = bundles[:3] == ["@deepseek-ai/dsh-base", "dsh-better-sidebar", "custom-bundle"]
        backup = probe / "package.json.bak-t143"
        backup_ok = backup.is_file() and json.loads(backup.read_text(encoding="utf-8")) == original
        idempotent = result.get("second") is False
        record("P4 行为探针", no_enterprise and has_presets and order_ok and backup_ok and idempotent,
               f"bundles={bundles} backup={backup_ok} idempotent={idempotent}")
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def check_p4_materialization() -> None:
    probe = Path(tempfile.mkdtemp(prefix="wn-t143-materialize-"))
    try:
        profile = probe / "profile"
        runtime = probe / "runtime"
        node_modules = profile / "node_modules"
        runtime_modules = runtime / "node_modules"
        (profile / "node_modules" / "yaml").mkdir(parents=True)
        (profile / "node_modules" / "yaml" / "index.js").write_text("partial", encoding="utf-8")
        (profile / "package.json").write_text(json.dumps({
            "name": "dsh-profile-desktop",
            "private": True,
            "dependencies": {
                "dsh-better-sidebar": "0.25.0",
                "dsh-claude-style": "0.13.2",
                "@linxin666/dsh-client-ui-skill-explorer": "0.4.6",
            },
            "dsh": {"profile": {"bundles": [
                "@deepseek-ai/dsh-base",
                "@deepseek-ai/dsh-web-app",
                "dsh-better-sidebar",
                "dsh-claude-style",
                "@linxin666/dsh-client-ui-skill-explorer",
            ]}},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (profile / "cordis.patch.yml").write_text("[]\n", encoding="utf-8")

        packages = {
            "dsh-better-sidebar": {"name": "dsh-better-sidebar", "version": "0.25.0",
                                   "dependencies": {"yaml": "^2.9.1"}},
            "dsh-claude-style": {"name": "dsh-claude-style", "version": "0.13.2"},
            "@linxin666/dsh-client-ui-skill-explorer": {
                "name": "@linxin666/dsh-client-ui-skill-explorer", "version": "0.4.6",
            },
            "dshmarket": {"name": "dshmarket", "version": "1.66.42",
                          "dependencies": {"js-yaml": "^4.3.2", "undici": "^7.29.1"}},
            "yaml": {"name": "yaml", "version": "2.9.1"},
            "js-yaml": {"name": "js-yaml", "version": "4.3.2"},
            "undici": {"name": "undici", "version": "7.29.1"},
        }
        for name, manifest in packages.items():
            package = runtime_modules.joinpath(*name.split("/"))
            package.mkdir(parents=True, exist_ok=True)
            (package / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
            (package / "index.js").write_text("export default {}\n", encoding="utf-8")

        source = (DESKTOP / "src" / "profile-bundle-backfill.ts").as_uri()
        script = probe / "probe.mjs"
        script.write_text(
            "import { backfillProfileMarketPlugin, materializePresetPlugins } from " + json.dumps(source) + "\n"
            "const profile = process.argv[2]\n"
            "const runtime = process.argv[3]\n"
            "const seeded = backfillProfileMarketPlugin(profile)\n"
            "const seededAgain = backfillProfileMarketPlugin(profile)\n"
            "const first = materializePresetPlugins(profile, runtime)\n"
            "const second = materializePresetPlugins(profile, runtime)\n"
            "console.log(JSON.stringify({ seeded, seededAgain, first, second }))\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [NODE, "--import", "tsx/esm", str(script), str(profile), str(runtime)],
            cwd=str(UPSTREAM), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            record("P4 市场与依赖闭包探针", False, f"exit={proc.returncode} {(proc.stderr or proc.stdout)[-500:]}")
            return
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        patch = read(profile / "cordis.patch.yml")
        required = (
            profile / "node_modules" / "dshmarket" / "package.json",
            profile / "node_modules" / "yaml" / "package.json",
            profile / "node_modules" / "js-yaml" / "package.json",
            profile / "node_modules" / "undici" / "package.json",
        )
        ok = (
            result["seeded"] is True
            and result["seededAgain"] is False
            and "- insert:" in patch
            and "- id: dsh-market" in patch
            and "name: 'dshmarket'" in patch
            and all(path.is_file() for path in required)
            and result["second"]["copied"] == []
        )
        record("P4 市场与依赖闭包探针", ok,
               f"market_insert={'- insert:' in patch and '- id: dsh-market' in patch} repaired={[p.name for p in required]} "
               f"first_copied={result['first']['copied']} second_copied={result['second']['copied']}")
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def check_p5() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    expected = {item["file"]: item["name"] for item in lock.get("packages", []) if "file" in item}
    produced = {path.name for path in PACKED.glob("*.tgz")}
    enterprise = sorted(name for name in produced if name.startswith("worknexus-"))
    roots = {
        "dshmarket",
        "dsh-better-sidebar",
        "dsh-claude-style",
        "@linxin666/dsh-client-ui-skill-explorer",
    }
    root_files = {item["file"] for item in lock.get("packages", []) if item.get("name") in roots}
    ok = (len(produced) == len(expected) and not enterprise and root_files.issubset(produced))
    record("P5 个人预置包集", ok,
           f"tgz={len(produced)}/{len(expected)} enterprise={enterprise or '无'} roots={len(root_files)}")


def check_p6() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "package_desktop_win_unsigned.py"), "--dry-run"],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    record("P6 出包 dry-run", proc.returncode == 0, f"exit={proc.returncode} {(proc.stdout or proc.stderr)[-200:]}")


def check_p9() -> None:
    enterprise_clean = False
    if ENTERPRISE_REPO.is_dir():
        proc = subprocess.run([GIT, "-C", str(ENTERPRISE_REPO), "status", "--porcelain"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        enterprise_clean = proc.returncode == 0 and not proc.stdout.strip()
    tracked = subprocess.run([GIT, "-C", str(REPO), "ls-files", "bundles", "plugins", "packages", "services"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
    no_tracked = not tracked.stdout.strip()
    record("P9 企业仓干净 / 本仓无企业 tracked", enterprise_clean and no_tracked,
           f"enterprise_clean={enterprise_clean} no_tracked={no_tracked}")


def main() -> int:
    check_p1()
    check_p2()
    check_p3()
    check_p4_static()
    check_p4_behavior()
    check_p4_materialization()
    check_p5()
    check_p6()
    check_p9()
    failed = [name for name, ok, _ in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failed)} [OK] / {len(failed)} [FAIL]（共 {len(RESULTS)} 条）")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
