#!/usr/bin/env python
"""T-005 探针：企业 bundle 预置与 protected 可行性验证。

目的（对应 docs/技术决策-企业bundle预置验证.md）：
1. 在隔离的 DSH_HOME 下复现「第一方 bundle 预置」（第三方 先例：
   profile package.json 的 dsh.profile.bundles + link: 依赖）。
2. 用 dsh 自带的 --dump-default-config / --dump-config 观察企业 bundle
   落在哪个 bundle 段，以判定它是否会被原生恢复流程当作可禁用的第三方 bundle。

纪律：
- 只在仓库内 .dsh-check/（已在 .gitignore）下操作，绝不触碰用户真实 ~/.dsh。
- 只读本机参照运行时（第三方 内置 dsh 0.1.7-alpha.2）；它是参照物不是锁定基线。
- 逐项输出 [OK]/[FAIL]；存在 [FAIL] 时退出码 1。

用法：python scripts/probe_bundle_preload.py
环境变量：DSH_REF_BIN  参照 dsh 入口（默认取本机 第三方 内置副本）
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PROBE_HOME = REPO / ".dsh-check" / "t005"
PROFILE = "ent"
ENT_BUNDLE_NAME = "@worknexus/ent-core"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def default_dsh_bin() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    p = Path(appdata) / "ThirdPartyApp" / "prod" / "harness" / "profiles" / "node_modules"
    p = p / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
    return p if p.exists() else None


def run_dsh(bin_js: Path, args: list[str], home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DSH_HOME"] = str(home)
    return subprocess.run(
        ["node", str(bin_js), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )


def write_ent_bundle(root: Path) -> Path:
    pkg_dir = root / "ent-bundle"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": ENT_BUNDLE_NAME,
        "version": "0.0.1-probe",
        "private": True,
        "type": "module",
        "main": "index.js",
        # 实测要求（见交付说明）：bundle 必须声明 dsh.bundle.patch，否则被 skip
        "dsh": {
            "bundle": {"patch": "./cordis.patch.yml"},
            "protected": True,
            "hostInfrastructure": True,
        },
    }
    (pkg_dir / "package.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # bundle patch 语义（实测）：用 `- insert:` 新增行；直接写 `- id:` 是覆盖已存在的行。
    (pkg_dir / "cordis.patch.yml").write_text(
        "- insert:\n"
        "    - id: ent-core-probe\n"
        "      name: '@worknexus/ent-core'\n",
        encoding="utf-8",
    )
    (pkg_dir / "index.js").write_text(
        "export const name = 'ent-core-probe';\nexport function apply() {}\n", encoding="utf-8"
    )
    return pkg_dir


def write_profile(home: Path, bundle_dir: Path) -> Path:
    profile_dir = home / "profiles" / PROFILE
    profile_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": f"dsh-profile-{PROFILE}",
        "private": True,
        "dependencies": {ENT_BUNDLE_NAME: f"link:{bundle_dir.as_posix()}"},
        "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", ENT_BUNDLE_NAME], "patchReload": "live"}},
        "type": "module",
    }
    path = profile_dir / "package.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    link_first_party_bundle(profile_dir, bundle_dir)
    return path


def link_first_party_bundle(profile_dir: Path, bundle_dir: Path) -> str:
    """把第一方 bundle 放到 profile 的 node_modules 下，模拟 `link:` 已安装。

    Windows 上优先用目录联接（junction，无需管理员）；失败则回退为目录复制。
    """
    scope = profile_dir / "node_modules" / "@worknexus"
    scope.mkdir(parents=True, exist_ok=True)
    dest = scope / "ent-core"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    try:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dest), str(bundle_dir)],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return "junction"
    except Exception:
        shutil.copytree(bundle_dir, dest, dirs_exist_ok=True)
        return "copy"


def segments(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"<head>": []}
    current = "<head>"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# == "):
            current = s[len("# == ") :].strip()
            out.setdefault(current, [])
        else:
            out[current].append(line)
    return out


def main() -> int:
    bin_js = Path(os.environ["DSH_REF_BIN"]) if os.environ.get("DSH_REF_BIN") else default_dsh_bin()
    if bin_js is None or not bin_js.exists():
        record(False, "参照 dsh 入口不存在（设置 DSH_REF_BIN 或安装本机 第三方 内置副本）")
        return finish()
    record(True, f"参照 dsh 入口就位: {bin_js}")

    expected_parent = (REPO / ".dsh-check").resolve()
    if not str(PROBE_HOME.resolve()).startswith(str(expected_parent)):
        record(False, f"隔离目录越界，拒绝删除: {PROBE_HOME}")
        return finish()
    if PROBE_HOME.exists():
        shutil.rmtree(PROBE_HOME)
    PROBE_HOME.mkdir(parents=True, exist_ok=True)
    record(True, f"隔离 DSH_HOME: {PROBE_HOME}")

    ver = run_dsh(bin_js, ["--version"], PROBE_HOME)
    record(
        ver.returncode == 0 and bool(ver.stdout.strip()),
        f"参照 dsh 版本: {ver.stdout.strip() or ver.stderr.strip()}（参照物，非锁定基线）",
    )

    bundle_dir = write_ent_bundle(PROBE_HOME)
    prof_pkg = write_profile(PROBE_HOME, bundle_dir)
    record(True, f"已写入 profile 定义: {prof_pkg.relative_to(REPO)}")

    dflt = run_dsh(bin_js, ["--profile", PROFILE, "--dump-default-config"], PROBE_HOME)
    dflt_segs: dict[str, list[str]] = {}
    if dflt.returncode == 0 and dflt.stdout.strip():
        record(True, "--dump-default-config 可运行并输出默认 profile 树")
        dflt_segs = segments(dflt.stdout)
        # 实测语义：dsh.profile.bundles 属 profile 层（非用户覆盖层），
        # 因此默认树与本层都应包含企业 bundle 段。
        record(
            ENT_BUNDLE_NAME in dflt_segs,
            "企业 bundle 位于 profile 的 bundle 段（出现在 --dump-default-config 中，说明不属于可被用户层移除的覆盖项）",
        )
    else:
        record(False, f"--dump-default-config 失败: {(dflt.stderr or dflt.stdout).strip()[:300]}")

    comp = run_dsh(bin_js, ["--profile", PROFILE, "--dump-config"], PROBE_HOME)
    raw = comp.stdout or ""
    if comp.returncode == 0 and raw.strip():
        record(True, "--dump-config 可运行并输出组合 profile 树")
    else:
        record(False, f"--dump-config 失败: {(comp.stderr or raw).strip()[:300]}")

    comp_segs = segments(raw)
    headers = [k for k in comp_segs if k != "<head>"]
    print("    -- 组合树 bundle 段（原始顺序）--")
    for k in headers:
        print(f"       - {k}")

    ent_present = ENT_BUNDLE_NAME in comp_segs
    base_i = next((i for i, k in enumerate(headers) if k.startswith("@deepseek-ai/dsh-base")), None)
    ent_i = next((i for i, k in enumerate(headers) if k == ENT_BUNDLE_NAME), None)
    if ent_present:
        record(True, f"企业 bundle 出现在组合树中（段: {ENT_BUNDLE_NAME}）")
        record(
            base_i is not None and ent_i is not None and ent_i > base_i,
            f"企业 bundle 段位于官方 bundle 之后（base@{base_i} -> ent@{ent_i}）",
        )
    else:
        record(False, "企业 bundle 未出现在组合树（已作为未验证项登记）")

    # 3b) 决定性探针：用户层能否禁用预置的企业 bundle 条目
    user_patch = PROBE_HOME / "profiles" / PROFILE / "cordis.patch.yml"
    user_patch.write_text(
        "- id: ent-core-probe\n  disabled: true\n",
        encoding="utf-8",
    )
    disabled_run = run_dsh(bin_js, ["--profile", PROFILE, "--dump-config"], PROBE_HOME)
    disabled_raw = disabled_run.stdout or ""
    ent_row_disabled = False
    lines = disabled_raw.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("- id: ent-core-probe"):
            tail = "\n".join(lines[i : i + 5])
            ent_row_disabled = "disabled: true" in tail
            break
    if disabled_run.returncode == 0 and ent_row_disabled:
        record(
            True,
            "用户层 patch **可以**把企业 bundle 条目置为 disabled（实测）→ 原生恢复/用户覆盖确实能关掉企业入口",
        )
    elif disabled_run.returncode == 0:
        record(
            True,
            "用户层 patch 未能把企业 bundle 条目置为 disabled（实测）→ 预置条目对用户层覆盖有抵抗",
        )
    else:
        record(
            False,
            f"用户层禁用探针执行失败: {(disabled_run.stderr or disabled_raw).strip()[:300]}",
        )

    summary = {
        "probe_home": str(PROBE_HOME),
        "dsh_ref": str(bin_js),
        "dsh_ref_version": ver.stdout.strip(),
        "default_bundle_segments": list(dflt_segs.keys()),
        "composed_bundle_segments": headers,
        "ent_bundle_present": ent_present,
        "default_config_exit": dflt.returncode,
        "dump_config_exit": comp.returncode,
        "user_layer_can_disable_ent_entry": ent_row_disabled,
    }
    out_file = REPO / ".dsh-check" / "t005-probe-summary.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    record(True, f"探针摘要已写入 {out_file.relative_to(REPO)}")
    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for o, _ in RESULTS if o)
    bad = sum(1 for o, _ in RESULTS if not o)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
