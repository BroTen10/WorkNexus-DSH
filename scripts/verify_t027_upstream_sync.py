#!/usr/bin/env python
"""T-027 门禁：上游同步门禁（rebase 演练 + 行为变化评审 + 日落扫描）。

流程（对应派发卡附录 A §T-027 的 3 步 + 增补 S1/S2/S3）：
  Y1  前置与上游 tag 核对（`git ls-remote --tags`；无新 tag → 走模拟演练）
  Y2  隔离演练场（`git clone --shared` 到 .dsh-check/t027，绝不触碰真实树）
  Y3  我方差异集快照分支（`git apply` diffset-01-brand.patch → 提交）
  Y4  构造「模拟上游新版本」（按 configs/sync/upstream-simulation.*.json 逐条改动）
  Y5  真实 rebase：收集冲突集，断言冲突 ⊆ 预期集合且非空
  Y6  冲突处置：按固定规则解析（官方基线 + 重放品牌规则 / 品牌资产以我方为准 / 双方追加并存）
  Y7  解析不变量：品牌合规不破、官方新增不丢、合规文件字节不变、品牌资产以我方为准
  Y8  行为变化清单（每条必须有跟随 / 不跟随 / 需改需求 三选一的处置）
  Y9  日落扫描（上游废弃/改名的符号在我方仓库的引用点必须全部有处置）
  Y10 构建（当前树 `pnpm --filter @deepseek-ai/dsh-desktop run build`；--no-build 可跳过）
  Y11 冒烟：我方门禁子集（T-021 品牌 / T-023 bundle / T-029 契约骨架）全绿
  Y12 演练记录六段 + 冲突项 + 处置 + 行为变化清单 + 日落扫描结果
  Y13 无长期分叉：演练分支无未处置冲突、工作树干净

用法：
  python scripts/verify_t027_upstream_sync.py
  python scripts/verify_t027_upstream_sync.py --no-build
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
PATCH = REPO / "patches" / "diffset-01-brand.patch"
MANIFEST = REPO / "configs" / "sync" / "upstream-simulation.0.2.0-rc.3.json"
DOC = REPO / "docs" / "上游同步演练记录.md"
WORK = REPO / ".dsh-check" / "t027"
SANDBOX = WORK / "upstream"
REPORT = WORK / "sync-report.json"

BASE_TAG = "dsh-v0.2.0-rc.2"
FORK_BRANCH = "worknexus-fork"
SIM_BRANCH = "upstream-sim"

# 品牌差异集里的文本替换规则（用于冲突解析时「重放品牌规则」）
BRAND_TEXT_RULES = [
    ("DeepSeek Harness", "WorkNexus-DSH"),
]

# 二进制品牌资产：冲突时一律以我方为准（品牌白名单 1.2）
BRAND_BINARY_PATHS = [
    "apps/desktop/resources/icon.png",
    "apps/desktop/resources/icon-windows.png",
    "apps/desktop/resources/icon-macos.png",
    "apps/desktop/resources/tray-windows.ico",
]

# 必须与基线逐字节一致的合规文件（同 T-021 G4）
FROZEN = [
    "LICENSE",
    "BRAND_GUIDELINES.md",
    "BRAND_GUIDELINES.zh.md",
    "BRAND_GUIDELINES.i18n.yaml",
    "THIRD_PARTY_NOTICES.md",
]

RESULTS: list[tuple[bool, str]] = []
RESOLUTIONS: list[dict] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def info(detail: str) -> None:
    print(f"[INFO] {detail}")


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for flag, _ in RESULTS if flag)
    bad = sum(1 for flag, _ in RESULTS if not flag)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


def run(args: list[str], cwd: Path, env: dict | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=timeout)


def git(args: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess:
    result = run(["git", *args], cwd)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {result.stderr[-300:]}")
    return result


def git_bytes(args: list[str], cwd: Path) -> bytes:
    """取原始字节（避免文本模式的换行翻译破坏逐字节比对）。"""
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, timeout=300).stdout


def rmtree_robust(path: Path) -> None:
    """删除目录树，兼容 Windows 上 git 对象的只读位。"""
    def handle(func, target, _exc):  # noqa: ANN001
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    for _ in range(3):
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onexc=handle)
        except TypeError:
            shutil.rmtree(path, onerror=handle)
        except OSError:
            continue


def apply_manifest(root: Path, manifest: dict) -> list[str]:
    """把模拟上游改动写进演练场，返回已生效条目的说明；find 未命中即报错。"""
    applied: list[str] = []
    for change in manifest["changes"]:
        path = root / change["path"]
        op = change["op"]
        if op == "replace":
            text = path.read_text(encoding="utf-8")
            if change["find"] not in text:
                raise RuntimeError(f"模拟改动未命中（{change['path']}）: {change['find']!r}")
            path.write_text(text.replace(change["find"], change["replace"], 1), encoding="utf-8")
        elif op == "appendText":
            with path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(change["text"])
        else:
            raise RuntimeError(f"未知的模拟操作: {op}")
        applied.append(f"{change['kind']}: {change['path']}")
    return applied


def brand_rewrite(text: str) -> str:
    for old, new in BRAND_TEXT_RULES:
        text = text.replace(old, new)
    return text


def resolve_conflicts(root: Path, conflicts: list[str], base_rev: str) -> list[dict]:
    """按固定规则解析冲突。返回处置记录。"""
    out: list[dict] = []
    baseline_readme = git_bytes(["show", f"{base_rev}:README.md"], root)
    fork_readme = git_bytes(["show", f"{FORK_BRANCH}:README.md"], root)
    our_block = fork_readme[len(baseline_readme):] if fork_readme.startswith(baseline_readme) else b""

    for rel in conflicts:
        if rel in BRAND_BINARY_PATHS:
            git(["checkout", "--theirs", "--", rel], root, check=True)
            out.append({"path": rel, "rule": "品牌资产以我方为准（--theirs）", "note": "白名单 1.2"})
        elif rel.endswith("src/locale.ts"):
            git(["checkout", "--ours", "--", rel], root, check=True)
            path = root / rel
            path.write_text(brand_rewrite(path.read_text(encoding="utf-8")), encoding="utf-8")
            out.append({"path": rel, "rule": "以官方为基线 + 重放品牌替换（--ours 后 DeepSeek Harness → WorkNexus-DSH）",
                        "note": "白名单 1.3（T-021 增补）"})
        elif rel == "README.md":
            git(["checkout", "--ours", "--", rel], root, check=True)
            path = root / rel
            data = path.read_bytes()
            if not data.endswith(b"\n"):
                data += b"\n"
            path.write_bytes(data + our_block)
            out.append({"path": rel, "rule": "上游追加段与我方发行版小节并存（--ours + 重放我方追加块）",
                        "note": "白名单 1.4"})
        else:
            out.append({"path": rel, "rule": "未处置（需人工裁决）", "note": "阻塞单"})
    return out


def sunset_scan(tokens: list[str]) -> dict[str, list[str]]:
    """在我方仓库（排除 repos/ 与 .dsh-check/）扫描日落符号的引用点。"""
    tracked = run(["git", "ls-files"], REPO).stdout.splitlines()
    hits: dict[str, list[str]] = {}
    for token in tokens:
        found: list[str] = []
        for rel in tracked:
            if rel.startswith("repos/") or rel.startswith(".dsh-check/"):
                continue
            path = REPO / rel
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if token in text:
                found.append(rel)
        hits[token] = sorted(found)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true", help="跳过桌面端构建")
    args = ap.parse_args()

    # ── Y1 前置与上游 tag 核对 ──
    if not (UPSTREAM / ".git").exists() or not PATCH.exists() or not MANIFEST.exists():
        record(False, "前置缺失：上游 fork 仓库 / 差异集补丁 / 模拟清单")
        return finish()
    base_rev = git(["rev-parse", "HEAD"], UPSTREAM).stdout.strip()
    record(bool(base_rev), f"Y1 上游 fork 基线提交 = {base_rev[:8]}（{BASE_TAG}）")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    record(manifest["basedOn"] == BASE_TAG, f"Y1 模拟清单基于 {manifest['basedOn']}")
    remote = run(["git", "ls-remote", "--tags", "--refs",
                  "https://github.com/deepseek-ai/deepseek-harness.git"], REPO, timeout=120)
    newest = ""
    if remote.returncode == 0:
        tags = [line.split("refs/tags/", 1)[1].strip() for line in remote.stdout.splitlines() if "refs/tags/" in line]
        versioned = sorted(t for t in tags if t.startswith("dsh-v"))
        newest = versioned[-1] if versioned else ""
        info(f"上游 tag 共 {len(versioned)} 个，最新 = {newest}；基线 = {BASE_TAG}")
        record(newest == BASE_TAG, "Y1 上游尚无新于基线的 tag（演练按模拟新版本进行）")
    else:
        info("上游 tag 查询失败（网络/凭据），演练按模拟新版本进行")
        record(True, "Y1 上游 tag 查询不可用 → 记入 C 类未验证项，演练继续")

    # ── Y2 隔离演练场 ──
    WORK.mkdir(parents=True, exist_ok=True)
    if SANDBOX.exists():
        rmtree_robust(SANDBOX)
    clone = run(["git", "clone", "--shared", "--quiet", str(UPSTREAM), str(SANDBOX)], WORK, timeout=600)
    record(clone.returncode == 0 and (SANDBOX / ".git").exists(), f"Y2 隔离演练场就绪: {SANDBOX.relative_to(REPO).as_posix()}")
    if clone.returncode != 0:
        return finish()
    git(["config", "user.email", "codex@worknexus.local"], SANDBOX, check=True)
    git(["config", "user.name", "WorkNexus Sync Drill"], SANDBOX, check=True)
    git(["config", "core.autocrlf", "false"], SANDBOX, check=True)

    # ── Y3 我方差异集快照 ──
    git(["checkout", "-q", "-b", FORK_BRANCH], SANDBOX, check=True)
    applied = git(["apply", "--binary", "--whitespace=nowarn", str(PATCH)], SANDBOX)
    record(applied.returncode == 0, f"Y3 差异集补丁可干净应用（exit={applied.returncode}）")
    if applied.returncode != 0:
        info(applied.stderr[-400:])
        return finish()
    git(["add", "-A"], SANDBOX, check=True)
    git(["commit", "-q", "-m", "chore: T-021 品牌差异集快照"], SANDBOX, check=True)
    fork_files = [line for line in git(["diff", "--name-only", "HEAD~1", "HEAD"], SANDBOX, check=True).stdout.splitlines() if line]
    # 12 = T-021 的 11 个落点 + 2026-09-30 追加的 apps/desktop/package.json（productName 决定
    # %APPDATA% 目录名，见差异集清单 §2.01）。
    record(len(fork_files) == 12, f"Y3 差异集快照含 12 个文件（实测 {len(fork_files)}）")

    # ── Y4 模拟上游新版本 ──
    git(["checkout", "-q", "-b", SIM_BRANCH, base_rev], SANDBOX, check=True)
    try:
        sim_applied = apply_manifest(SANDBOX, manifest)
        sim_ok, sim_detail = True, f"{len(sim_applied)} 条全部生效"
    except Exception as exc:  # noqa: BLE001
        sim_ok, sim_detail = False, str(exc)
    record(sim_ok, f"Y4 模拟上游 {manifest['simulatedVersion']} 改动全部生效（{sim_detail}）")
    if not sim_ok:
        return finish()
    git(["add", "-A"], SANDBOX, check=True)
    git(["commit", "-q", "-m", f"upstream: {manifest['simulatedVersion']}（模拟）"], SANDBOX, check=True)
    sim_rev = git(["rev-parse", "HEAD"], SANDBOX, check=True).stdout.strip()

    # ── Y5 真实 rebase ──
    git(["checkout", "-q", FORK_BRANCH], SANDBOX, check=True)
    rebase = git(["rebase", SIM_BRANCH], SANDBOX)
    conflicts = [line for line in
                 git(["diff", "--name-only", "--diff-filter=U"], SANDBOX, check=True).stdout.splitlines() if line]
    expected = set(manifest["expectedConflictPaths"])
    unexpected = [path for path in conflicts if path not in expected]
    record(bool(conflicts), f"Y5 rebase 产生真实冲突 = {conflicts}（rebase exit={rebase.returncode}）")
    record(not unexpected, f"Y5 无预期外的冲突路径（意外: {unexpected or '无'}）")
    if not conflicts or unexpected:
        git(["rebase", "--abort"], SANDBOX)
        return finish()

    # ── Y6 冲突处置 ──
    resolutions = resolve_conflicts(SANDBOX, conflicts, base_rev)
    unresolved = [item for item in resolutions if item["rule"].startswith("未处置")]
    record(not unresolved, f"Y6 冲突全部有处置规则（未处置: {[i['path'] for i in unresolved] or '无'}）")
    git(["add", "-A"], SANDBOX, check=True)
    env = dict(os.environ, GIT_EDITOR="true")
    cont = run(["git", "rebase", "--continue"], SANDBOX, env=env, timeout=300)
    record(cont.returncode == 0, f"Y6 rebase 完成（exit={cont.returncode}）")
    still = [line for line in
             git(["diff", "--name-only", "--diff-filter=U"], SANDBOX, check=True).stdout.splitlines() if line]
    record(not still, f"Y6 无残留未合并路径（{still or '无'}）")

    # ── Y7 解析不变量 ──
    locale_text = (SANDBOX / "apps/desktop/src/locale.ts").read_text(encoding="utf-8")
    record(locale_text.count("DeepSeek Harness") == 0 and locale_text.count("WorkNexus-DSH") >= 20,
           f"Y7 品牌合规不破（DeepSeek Harness={locale_text.count('DeepSeek Harness')}，"
           f"WorkNexus-DSH={locale_text.count('WorkNexus-DSH')}）")
    record("releaseChannel:" in locale_text, "Y7 官方新增文案键被保留（releaseChannel）")
    readme = (SANDBOX / "README.md").read_text(encoding="utf-8", errors="replace")
    record("What's new in 0.2.0-rc.3" in readme and "WorkNexus-DSH distribution" in readme,
           "Y7 README 同时含上游新节与我方发行版小节")
    record((SANDBOX / "WORKNEXUS-RELEASE-NOTES.md").exists(), "Y7 我方发行说明仍在")
    version_ok = json.loads((SANDBOX / "apps/desktop/package.json").read_text(encoding="utf-8"))["version"] == "0.2.0-rc.3"
    record(version_ok, "Y7 跟随上游版本推进（apps/desktop version = 0.2.0-rc.3）")
    ours_icon = (UPSTREAM / "apps/desktop/resources/icon.png").read_bytes()
    merged_icon = (SANDBOX / "apps/desktop/resources/icon.png").read_bytes()
    record(ours_icon == merged_icon, "Y7 品牌资产以我方为准（解析后 icon.png 与我方逐字节一致）")
    frozen_bad = []
    for rel in FROZEN:
        base_bytes = git_bytes(["show", f"{base_rev}:{rel}"], SANDBOX)
        current = (SANDBOX / rel).read_bytes() if (SANDBOX / rel).exists() else b""
        if base_bytes and current != base_bytes:
            frozen_bad.append(rel)
    record(not frozen_bad, f"Y7 合规文件与基线逐字节一致（不一致: {frozen_bad or '无'}）")

    # ── Y13 无长期分叉 ──
    status = git(["status", "--porcelain"], SANDBOX, check=True).stdout.strip()
    record(not status, f"Y13 演练分支工作树干净、无未处置冲突（{status or 'clean'}）")

    # ── Y8/Y9 行为变化清单与日落扫描 ──
    behaviors = [c for c in manifest["changes"] if c["kind"] in {"behavior", "sunset"}]
    tokens = [token for change in behaviors for token in change.get("deprecatedTokens", [])]
    hits = sunset_scan(tokens)
    behavior_list = [{"path": c["path"], "kind": c["kind"], "note": c["note"],
                      "tokens": c.get("deprecatedTokens", [])} for c in behaviors]
    record(len(behavior_list) >= 2, f"Y8 行为变化/日落候选清单 = {len(behavior_list)} 条")
    record(all(hits[token] for token in tokens),
           f"Y9 日落扫描命中我方引用点（{ {t: len(hits[t]) for t in tokens} }）")
    known = {"DSH_DESKTOP_AUTO_UPDATE_ENV=test": "跟随：上游通道口径变化时同步更新我方配置模板与文档引用",
             "desktopUpdateMetadataFilename": "跟随：上游重命名导出时同步更新我方门禁脚本引用"}
    record(all(token in known for token in tokens), "Y9 每个日落符号都已有处置口径（跟随/不跟随/需改需求）")

    # ── Y10 构建 ──
    if args.no_build:
        info("Y10 构建已按 --no-build 跳过")
    else:
        env = dict(os.environ, ELECTRON_SKIP_BINARY_DOWNLOAD="1")
        build = run(["node", str(UPSTREAM / "node_modules" / "pnpm" / "bin" / "pnpm.mjs"),
                     "--filter", "@deepseek-ai/dsh-desktop", "run", "build"], UPSTREAM, env=env, timeout=1800)
        record(build.returncode == 0, f"Y10 当前树桌面端构建退出码 {build.returncode}")

    # ── Y11 冒烟（我方门禁子集） ──
    smoke = []
    for script in ("verify_t021_brand.py", "verify_t023_bundle.py", "verify_t029_skeleton.py"):
        result = run([sys.executable, str(REPO / "scripts" / script)], REPO, timeout=1200)
        smoke.append((script, result.returncode))
    record(all(code == 0 for _, code in smoke),
           f"Y11 冒烟门禁子集全绿（{', '.join(f'{name}={code}' for name, code in smoke)}）")

    # ── 产物：机器报告 ──
    report = {
        "baseTag": BASE_TAG,
        "baseRevision": base_rev,
        "simulatedVersion": manifest["simulatedVersion"],
        "simulatedRevision": sim_rev,
        "newestUpstreamTag": newest,
        "conflicts": conflicts,
        "expectedConflicts": sorted(expected),
        "resolutions": resolutions,
        "behaviorChanges": behavior_list,
        "sunsetScan": hits,
        "unresolvedProblems": [item["path"] for item in unresolved],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    info(f"机器报告: {REPORT.relative_to(REPO).as_posix()}")

    # ── Y12 演练记录 ──
    sections = ["## 1. 结论先行", "## 2. 改动清单", "## 3. 验证证据表",
                "## 4. 未验证项与边界", "## 5. 复现命令", "## 6. 下一步"]
    doc = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    missing = [section for section in sections if section not in doc]
    record(not missing, f"Y12 演练记录六段齐备（缺: {missing or '无'}）")
    record("冲突集" in doc and "日落扫描" in doc and "行为变化" in doc,
           "Y12 演练记录含冲突项、处置、行为变化清单与日落扫描结果")
    record(all(path in doc for path in conflicts) and all(token in doc for token in tokens),
           "Y12 演练记录逐条覆盖实际冲突路径与日落符号")

    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
