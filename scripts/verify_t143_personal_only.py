#!/usr/bin/env python
"""T-143 门禁：个人版宿主清理。

断言：
  P1  企业目录不存在（bundles/plugins/packages/services）
  P2  prepare-package-set.ts 无 @worknexus 根；默认 roots 只含 dshmarket
  P3  project-manager.ts profile bundles 无 @worknexus 或四个退役预置
  P4  profile-bundle-backfill.ts 清理企业/退役预置 + 保留市场；行为探针通过
  P5  .worknexus-packed 无企业 tgz；只含 dshmarket 根及其运行闭包
  P6  package_desktop_win_unsigned.py --dry-run 退出 0
  P7  隔离 profile 清理后无 @worknexus/*，备份存在且幂等
  P9  本仓无企业目录 tracked 文件；外部企业仓状态不纳入个人版门禁

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
    has_retired = any(name in text for name in ("dsh-better-sidebar", "dsh-claude-style", "@tt-a1i/archify-dsh", "@linxin666/dsh-client-ui-skill-explorer"))
    record("P2 包集根只含市场", not has_enterprise and has_market and not has_retired,
           f"@worknexus={has_enterprise} dshmarket={has_market} 退役预置={has_retired}")


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
    has_retired = any(name in text for name in ("dsh-better-sidebar", "dsh-claude-style", "@tt-a1i/archify-dsh", "@linxin666/dsh-client-ui-skill-explorer"))
    market_outside_bundles = "'dshmarket'" not in text
    record("P3 profile 初值无企业/退役 bundle / 市场不入 bundle", not hits and not has_retired and market_outside_bundles,
           f"企业 bundle={hits or '无'} 退役预置={has_retired} dshmarket_not_in_bundles={market_outside_bundles}")


def check_p4_static() -> None:
    text = read(DESKTOP / "src" / "profile-bundle-backfill.ts")
    has_prefix = "STALE_ENTERPRISE_BUNDLE_PREFIX = '@worknexus/'" in text
    has_filter = "startsWith(STALE_ENTERPRISE_BUNDLE_PREFIX)" in text
    has_backup = ".bak-t143" in text
    has_market = (
        "WORKNEXUS_MARKET_PLUGIN = 'dshmarket'" in text
        and "WORKNEXUS_MARKET_ENTRY_ID = 'dsh-market'" in text
        and "WORKNEXUS_MARKET_ENTRY = '../../dshmarket/lib/index.js'" in text
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
                "dsh-better-sidebar": "0.28.2",
                "dsh-claude-style": "0.19.6",
                "@tt-a1i/archify-dsh": "1.0.0",
                "@linxin666/dsh-client-ui-skill-explorer": "0.4.13",
                "custom-bundle": "2.0.0",
            },
            "dsh": {
                "profile": {
                    "bundles": [
                        "@deepseek-ai/dsh-base",
                        "@worknexus/ent-core",
                        "@worknexus/plugin-market",
                        "dsh-better-sidebar",
                        "dsh-claude-style",
                        "@tt-a1i/archify-dsh",
                        "@linxin666/dsh-client-ui-skill-explorer",
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
        dependencies = updated["dependencies"]
        no_enterprise = all(not name.startswith("@worknexus/") for name in bundles)
        retired = {"dsh-claude-style", "@tt-a1i/archify-dsh", "@linxin666/dsh-client-ui-skill-explorer", "dsh-better-sidebar"}
        no_retired = not retired.intersection(bundles) and not retired.intersection(dependencies)
        custom_preserved = bundles == ["@deepseek-ai/dsh-base", "custom-bundle"] and dependencies.get("custom-bundle") == "2.0.0"
        backup = probe / "package.json.bak-t143"
        backup_ok = backup.is_file() and json.loads(backup.read_text(encoding="utf-8")) == original
        idempotent = result.get("second") is False
        record("P4 行为探针", no_enterprise and no_retired and custom_preserved and backup_ok and idempotent,
               f"bundles={bundles} dependencies={dependencies} backup={backup_ok} idempotent={idempotent}")
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def check_p4_materialization() -> None:
    probe = Path(tempfile.mkdtemp(prefix="wn-t143-materialize-"))
    try:
        profile = probe / "profiles" / "desktop"
        runtime = probe / "runtime"
        node_modules = profile / "node_modules"
        runtime_modules = runtime / "node_modules"
        (profile / "node_modules" / "yaml").mkdir(parents=True)
        (profile / "node_modules" / "yaml" / "index.js").write_text("partial", encoding="utf-8")
        legacy_market = profile / "node_modules" / "dshmarket"
        legacy_market.mkdir(parents=True)
        (legacy_market / "package.json").write_text(
            json.dumps({"name": "dshmarket", "version": "1.73.7"}, ensure_ascii=False),
            encoding="utf-8",
        )
        for name, version in (
            ("dsh-better-sidebar", "0.28.2"),
            ("dsh-claude-style", "0.19.6"),
            ("@tt-a1i/archify-dsh", "1.0.0"),
            ("@linxin666/dsh-client-ui-skill-explorer", "0.4.13"),
        ):
            old_package = profile / "node_modules" / name
            old_package.mkdir(parents=True, exist_ok=True)
            (old_package / "package.json").write_text(
                json.dumps({"name": name, "version": version}, ensure_ascii=False),
                encoding="utf-8",
            )
        (profile / "package.json").write_text(json.dumps({
            "name": "dsh-profile-desktop",
            "private": True,
            "dependencies": {
                "dsh-better-sidebar": "0.28.2",
                "dsh-claude-style": "0.19.6",
                "@tt-a1i/archify-dsh": "1.0.0",
                "@linxin666/dsh-client-ui-skill-explorer": "0.4.13",
                "custom-bundle": "2.0.0",
            },
            "dsh": {"profile": {"bundles": [
                "@deepseek-ai/dsh-base",
                "@deepseek-ai/dsh-web-app",
                "dsh-claude-style",
                "@tt-a1i/archify-dsh",
                "@linxin666/dsh-client-ui-skill-explorer",
                "dsh-better-sidebar",
                "custom-bundle",
            ]}},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (profile / "cordis.patch.yml").write_text("[]\n", encoding="utf-8")

        packages = {
            "dshmarket": {"name": "dshmarket", "version": "1.73.7",
                          "dependencies": {"js-yaml": "^4.3.2", "undici": "^7.29.1"}},
            "js-yaml": {"name": "js-yaml", "version": "4.3.2",
                        "dependencies": {"argparse": "^2.0.1"}},
            "argparse": {"name": "argparse", "version": "2.0.1"},
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
            "import { backfillProfileBundles, backfillProfileMarketPlugin, materializePresetPlugins } from " + json.dumps(source) + "\n"
            "const profile = process.argv[2]\n"
            "const runtime = process.argv[3]\n"
            "const cleaned = backfillProfileBundles(profile)\n"
            "const seeded = backfillProfileMarketPlugin(profile)\n"
            "const seededAgain = backfillProfileMarketPlugin(profile)\n"
            "const first = materializePresetPlugins(profile, runtime)\n"
            "const second = materializePresetPlugins(profile, runtime)\n"
            "console.log(JSON.stringify({ cleaned, seeded, seededAgain, first, second }))\n",
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
        manifest = json.loads((profile / "package.json").read_text(encoding="utf-8"))
        required = (
            probe / "dshmarket" / "package.json",
            probe / "dshmarket" / "node_modules" / "js-yaml" / "package.json",
            probe / "dshmarket" / "node_modules" / "argparse" / "package.json",
            probe / "dshmarket" / "node_modules" / "undici" / "package.json",
        )
        explicit_path = "name: '../../dshmarket/lib/index.js'" in patch
        retired = {"dsh-claude-style", "@tt-a1i/archify-dsh", "@linxin666/dsh-client-ui-skill-explorer", "dsh-better-sidebar"}
        profile_bundles = set(manifest["dsh"]["profile"]["bundles"])
        profile_dependencies = set(manifest["dependencies"])
        retired_removed = (
            not retired.intersection(profile_bundles)
            and not retired.intersection(profile_dependencies)
            and all(not (profile / "node_modules" / name).exists() for name in retired)
        )
        ok = (
            result["cleaned"] is True
            and result["seeded"] is True
            and result["seededAgain"] is False
            and "- insert:" in patch
            and "- id: dsh-market" in patch
            and explicit_path
            and all(path.is_file() for path in required)
            and not legacy_market.exists()
            and retired_removed
            and "custom-bundle" in profile_bundles
            and manifest["dependencies"].get("custom-bundle") == "2.0.0"
            and result["second"]["copied"] == []
        )
        record("P4 市场与依赖闭包探针", ok,
               f"cleaned={result['cleaned']} seeded={result['seeded']} seeded_again={result['seededAgain']} "
               f"market_insert={'- insert:' in patch and '- id: dsh-market' in patch} "
               f"explicit_path={explicit_path} "
               f"repaired={[str(p.relative_to(probe)) for p in required]} "
               f"missing={[str(p.relative_to(probe)) for p in required if not p.is_file()]} "
               f"legacy_removed={not legacy_market.exists()} "
               f"retired_removed={retired_removed} "
               f"first_copied={result['first']['copied']} second_copied={result['second']['copied']}")
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def check_p5() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    expected = {item["file"]: item["name"] for item in lock.get("packages", []) if "file" in item}
    produced = {path.name for path in PACKED.glob("*.tgz")}
    enterprise = sorted(name for name in produced if name.startswith("worknexus-"))
    retired = {"dsh-better-sidebar", "dsh-claude-style", "@tt-a1i/archify-dsh", "@linxin666/dsh-client-ui-skill-explorer"}
    root_names = {item["name"] for item in lock.get("packages", []) if item.get("role") == "bundle-root"}
    root_files = {item["file"] for item in lock.get("packages", []) if item.get("role") == "bundle-root"}
    retired_entries = sorted(name for name in root_names if name in retired)
    ok = (
        len(produced) == len(expected)
        and not enterprise
        and root_names == {"dshmarket"}
        and not retired_entries
        and root_files.issubset(produced)
    )
    record("P5 个人预置包集", ok,
           f"tgz={len(produced)}/{len(expected)} enterprise={enterprise or '无'} "
           f"roots={sorted(root_names)} retired={retired_entries or '无'}")


def check_p6() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "package_desktop_win_unsigned.py"), "--dry-run"],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    record("P6 出包 dry-run", proc.returncode == 0, f"exit={proc.returncode} {(proc.stdout or proc.stderr)[-200:]}")


def check_p9() -> None:
    enterprise_state = "不存在"
    if ENTERPRISE_REPO.is_dir():
        proc = subprocess.run([GIT, "-C", str(ENTERPRISE_REPO), "status", "--porcelain"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        enterprise_state = "外部仓干净" if proc.returncode == 0 and not proc.stdout.strip() else "外部仓有改动（不纳入）"
    tracked = subprocess.run([GIT, "-C", str(REPO), "ls-files", "bundles", "plugins", "packages", "services"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
    no_tracked = not tracked.stdout.strip()
    record("P9 本仓无企业 tracked", no_tracked,
           f"no_tracked={no_tracked} external={enterprise_state}")


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
