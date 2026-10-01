#!/usr/bin/env python
"""T-023 门禁：企业 bundle 预置与失败隔离。

断言：
  B1  bundle 包结构齐备（package.json / cordis.patch.yml / index.js / skeleton.js / failing.js）
  B2  package.json 声明 dsh.bundle.patch 且指向存在的文件（T-005 C-1）
  B3  patch 只用 `- insert:`，且不引用官方 bundle 的行 id（T-005 C-2/C-3）
  B4  组合树出现 `# == @worknexus/ent-core` 段，且位于官方 bundle 之后（真实探针）
  B5  企业 bundle 段出现在 --dump-default-config（属 profile 层，用户层无法摘除）
  B6  解析失败隔离：一行指向不存在的模块时，dsh 仍退出码 0 且官方段完整
  B7  启动失败隔离：启用故意失败的插件后，装配仍成功、官方段与企业段仍在
  B8  恢复入口：--restore 能修复被破坏的 bundles 清单，且不动其他 profile 数据

可选：--dsh-bin <path> 指定参照 dsh（默认取本机 第三方 内置副本）
单独使用：--restore <DSH_HOME>  只执行恢复入口
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "bundles" / "ent-core"
WORK = REPO / ".dsh-check" / "t023"
PROFILE = "ent"
BUNDLE_NAME = "@worknexus/ent-core"
OFFICIAL = ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-webapp-placeholder"]
OFFICIAL_REAL = "@deepseek-ai/dsh-base"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def find_dsh(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    p = Path(appdata) / "ThirdPartyApp" / "prod" / "harness" / "profiles" / "node_modules"
    p = p / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
    return p if p.exists() else None


def run_dsh(bin_js: Path, args: list[str], home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DSH_HOME"] = str(home)
    return subprocess.run(["node", str(bin_js), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=180)


def link_bundle(profile_dir: Path) -> None:
    scope = profile_dir / "node_modules" / "@worknexus"
    scope.mkdir(parents=True, exist_ok=True)
    dest = scope / "ent-core"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    try:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dest), str(BUNDLE)],
                       capture_output=True, text=True, timeout=60, check=True)
    except Exception:
        shutil.copytree(BUNDLE, dest, dirs_exist_ok=True)


def write_profile(home: Path, name: str, bundles: list[str], extra_entries: list[dict] | None = None) -> Path:
    d = home / "profiles" / name
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": f"dsh-profile-{name}",
        "private": True,
        "dependencies": {BUNDLE_NAME: f"link:{(BUNDLE).as_posix()}"},
        "dsh": {"profile": {"bundles": bundles, "patchReload": "live"}},
        "type": "module",
        # 恢复入口必须保留的商业数据（用于 B8 断言）
        "worknexus": {"spaceId": "space-probe", "orgId": "org-probe"},
    }
    p = d / "package.json"
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if extra_entries:
        lines = ["- insert:"]
        for e in extra_entries:
            lines.append(f"    - id: {e['id']}")
            lines.append(f"      name: '{e['name']}'")
        (d / "cordis.patch.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    link_bundle(d)
    return p


def segments(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"<head>": []}
    cur = "<head>"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# == "):
            cur = s[len("# == ") :].strip()
            out.setdefault(cur, [])
        else:
            out[cur].append(line)
    return out


def restore(home: Path) -> int:
    """恢复入口：只重写 dsh.profile.bundles，保证官方在前、企业 bundle 在后。"""
    fixed, broken = 0, 0
    profiles = home / "profiles"
    if not profiles.is_dir():
        print(f"[FAIL] 恢复入口：{profiles} 不存在")
        return 1
    for pkg in sorted(profiles.glob("*/package.json")):
        data = json.loads(pkg.read_text(encoding="utf-8"))
        prof = data.setdefault("dsh", {}).setdefault("profile", {})
        bundles = list(prof.get("bundles") or [])
        official = [b for b in bundles if b.startswith("@deepseek-ai/")]
        rest = [b for b in bundles if not b.startswith("@deepseek-ai/") and b != BUNDLE_NAME]
        target = official + rest + [BUNDLE_NAME]
        if not official:
            official = [OFFICIAL_REAL]
            target = [OFFICIAL_REAL] + rest + [BUNDLE_NAME]
        if bundles != target:
            broken += 1
            prof["bundles"] = target
            data.setdefault("dependencies", {})[BUNDLE_NAME] = f"link:{BUNDLE.as_posix()}"
            pkg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] 恢复 {pkg.parent.name}: bundles -> {target}")
        else:
            fixed += 1
    print(f"[OK] 恢复入口完成：已修复 {broken} 个 profile，{fixed} 个本就正确")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsh-bin")
    ap.add_argument("--restore", metavar="DSH_HOME")
    args = ap.parse_args()

    if args.restore:
        return restore(Path(args.restore))

    # B1
    need = ["package.json", "cordis.patch.yml", "index.js", "skeleton.js", "failing.js", "README.md"]
    missing = [f for f in need if not (BUNDLE / f).exists()]
    record(not missing, f"B1 bundle 包结构齐备（缺: {missing or '无'}）")

    pkg = json.loads((BUNDLE / "package.json").read_text(encoding="utf-8"))
    patch_rel = pkg.get("dsh", {}).get("bundle", {}).get("patch")
    record(bool(patch_rel) and (BUNDLE / str(patch_rel).lstrip("./")).exists(),
           f"B2 声明 dsh.bundle.patch = {patch_rel} 且文件存在")

    patch_text = (BUNDLE / "cordis.patch.yml").read_text(encoding="utf-8")
    ids = [l.strip().split("id:", 1)[1].strip() for l in patch_text.splitlines() if l.strip().startswith("- id:")]
    official_ids = {"tool-plugin-manager", "plugin-manager", "timer", "hmr", "llm", "session", "agent"}
    record("- insert:" in patch_text and not (set(ids) & official_ids),
           f"B3 patch 使用 `- insert:` 且不引用官方行 id（本包 id: {ids}）")

    bin_js = find_dsh(args.dsh_bin)
    if bin_js is None:
        record(False, "参照 dsh 不可用（用 --dsh-bin 指定）")
        return finish()
    record(True, f"参照 dsh: {bin_js}")

    expected_parent = (REPO / ".dsh-check").resolve()
    if not str(WORK.resolve()).startswith(str(expected_parent)):
        record(False, f"隔离目录越界: {WORK}")
        return finish()
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)

    # B4/B5：正常装配
    write_profile(WORK, PROFILE, [OFFICIAL_REAL, BUNDLE_NAME])
    comp = run_dsh(bin_js, ["--profile", PROFILE, "--dump-config"], WORK)
    comp_segs = segments(comp.stdout or "")
    headers = [k for k in comp_segs if k != "<head>"]
    ent_present = BUNDLE_NAME in comp_segs
    base_i = next((i for i, k in enumerate(headers) if k.startswith("@deepseek-ai/dsh-base")), None)
    ent_i = next((i for i, k in enumerate(headers) if k == BUNDLE_NAME), None)
    record(comp.returncode == 0 and ent_present and base_i is not None and ent_i is not None and ent_i > base_i,
           f"B4 组合树段顺序正确：{headers}（exit={comp.returncode}）")

    dflt = run_dsh(bin_js, ["--profile", PROFILE, "--dump-default-config"], WORK)
    record(BUNDLE_NAME in segments(dflt.stdout or ""),
           "B5 企业 bundle 段出现在默认树（profile 层，用户层无法摘除）")

    # B6：解析失败隔离
    write_profile(WORK, "ent-bad", [OFFICIAL_REAL, "@worknexus/does-not-exist"])
    bad = run_dsh(bin_js, ["--profile", "ent-bad", "--dump-config"], WORK)
    bad_segs = segments(bad.stdout or "")
    record(bad.returncode == 0 and any(k.startswith("@deepseek-ai/dsh-base") for k in bad_segs),
           f"B6 解析失败隔离：退出码 {bad.returncode}，官方段仍在（warning: {'skipping' in (bad.stdout + bad.stderr)}）")

    # B7：启动失败隔离（装配层证据）
    write_profile(WORK, "ent-fail", [OFFICIAL_REAL, BUNDLE_NAME],
                  extra_entries=[{"id": "ent-core-failing", "name": f"{BUNDLE_NAME}/failing"}])
    fail_run = run_dsh(bin_js, ["--profile", "ent-fail", "--dump-config"], WORK)
    fail_segs = segments(fail_run.stdout or "")
    record(fail_run.returncode == 0
           and any(k.startswith("@deepseek-ai/dsh-base") for k in fail_segs)
           and BUNDLE_NAME in fail_segs,
           f"B7 启动失败隔离（装配层）：退出码 {fail_run.returncode}，官方段与企业段均在")

    # B8：恢复入口
    broken_pkg = WORK / "profiles" / PROFILE / "package.json"
    data = json.loads(broken_pkg.read_text(encoding="utf-8"))
    data["dsh"]["profile"]["bundles"] = [BUNDLE_NAME]  # 破坏：企业在前且缺官方
    broken_pkg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    rc = restore(WORK)
    after = json.loads(broken_pkg.read_text(encoding="utf-8"))
    restored_bundles = after["dsh"]["profile"]["bundles"]
    preserved = after.get("worknexus", {})
    record(rc == 0
           and restored_bundles[0].startswith("@deepseek-ai/")
           and restored_bundles[-1] == BUNDLE_NAME
           and preserved == {"spaceId": "space-probe", "orgId": "org-probe"},
           f"B8 恢复入口修复 bundles={restored_bundles} 且其他数据保留={preserved}")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for o, _ in RESULTS if o)
    bad = sum(1 for o, _ in RESULTS if not o)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
