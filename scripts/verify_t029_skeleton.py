#!/usr/bin/env python
"""T-029 门禁：Host Core 契约骨架 bundle（P1 预置）。

断言：
  S1  契约包结构齐备（version/identity/space/permission/audit/usage/event/plugin/update + index + test）
  S2  契约包类型构建通过（tsc）
  S3  契约包单测通过（vitest，直接调 node 绕过 pnpm 的 builds 门禁）
  S4  八类契约 + P3 扩展契约⑨在构建产物中可导入，且契约版本为语义化 1.1.0
  S5  骨架 bundle 可被真实加载：describe() 返回契约版本与本包的三条「不承载」自述
  S6  负向：契约包不实现 AgentTransport、不引控制面（无 fetch/axios/http 调用）
  S7  真实探针：预置后组合树出现 `# == @worknexus/ent-core` 段，且骨架行在组合树中

用法：python scripts/verify_t029_skeleton.py
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
PKG = REPO / "packages" / "contracts"
BUNDLE = REPO / "bundles" / "ent-core"
WORK = REPO / ".dsh-check" / "t029"
PROFILE = "ent"
BUNDLE_NAME = "@worknexus/ent-core"
EXPECTED_VERSION = "1.1.0"

CONTRACT_FILES = [
    "version.ts", "identity.ts", "space.ts", "permission.ts",
    "audit.ts", "usage.ts", "event.ts", "plugin.ts", "update.ts",
    "knowledge.ts", "index.ts",
]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def find_dsh() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    p = Path(appdata) / "ThirdPartyApp" / "prod" / "harness" / "profiles" / "node_modules"
    p = p / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
    return p if p.exists() else None


def main() -> int:
    missing = [f for f in CONTRACT_FILES if not (PKG / "src" / f).exists()]
    missing += [] if (PKG / "test" / "contracts.test.ts").exists() else ["test/contracts.test.ts"]
    record(not missing, f"S1 契约包结构齐备（缺: {missing or '无'}）")

    tsc = node(str(PKG / "node_modules" / "typescript" / "bin" / "tsc"), "-p", "tsconfig.json", cwd=PKG)
    record(tsc.returncode == 0, f"S2 类型构建退出码 {tsc.returncode}"
           + ("" if tsc.returncode == 0 else f"（{tsc.stdout.strip()[:160]}）"))

    vit = node(str(PKG / "node_modules" / "vitest" / "vitest.mjs"), "run", cwd=PKG)
    tail = [l for l in (vit.stdout or "").splitlines() if "Tests" in l or "Test Files" in l]
    record(vit.returncode == 0, f"S3 单测退出码 {vit.returncode}（{' / '.join(t.strip() for t in tail)}）")

    probe = (
        "import('@worknexus/contracts').then(m=>{"
        "const need=['HOST_CORE_CONTRACT_VERSION','PERSONAL_IDENTITY','ROLES','DENY_ALL_POLICY',"
        "'AUDIT_SUMMARY_MAX_LENGTH','deriveTotalTokens','ENTERPRISE_EVENT_TOPICS','PERSONAL_MODE_GOVERNANCE',"
        "'KNOWLEDGE_HEALTH_STATES'];"
        "const miss=need.filter(k=>!(k in m));"
        "console.log(JSON.stringify({version:m.HOST_CORE_CONTRACT_VERSION,missing:miss,"
        "knowledgeStates:[...m.KNOWLEDGE_HEALTH_STATES].length}));})"
    )
    s4 = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((s4.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {}
    record(info.get("version") == EXPECTED_VERSION and info.get("missing") == []
           and info.get("knowledgeStates") == 4,
           f"S4 八类契约 + 契约⑨可导入，契约版本 = {info.get('version')}（缺: {info.get('missing')}）")

    s5 = node("--input-type=module", "-e",
              "import('./bundles/ent-core/skeleton.js').then(m=>console.log(JSON.stringify(m.describe())))",
              cwd=REPO)
    try:
        desc = json.loads((s5.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        desc = {}
    record(
        desc.get("ok") is True
        and desc.get("contractVersion") == EXPECTED_VERSION
        and desc.get("carriesBusinessData") is False
        and desc.get("connectsControlPlane") is False
        and desc.get("implementsAgentTransport") is False,
        f"S5 骨架可加载且自述正确（version={desc.get('contractVersion')}，三条自述="
        f"{desc.get('carriesBusinessData')}/{desc.get('connectsControlPlane')}/{desc.get('implementsAgentTransport')}）",
    )

    # 只在「去掉注释后的实际代码」里找禁止项——文档注释里会正当地出现
    # 「不实现 AgentTransport」这类表述，不能算命中。
    import re
    raw = "\n".join((PKG / "src" / f).read_text(encoding="utf-8") for f in CONTRACT_FILES)
    code = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = []
    if re.search(r"\bAgentTransport\b", code):
        hits.append("AgentTransport")
    for token in ("fetch(", "axios", "http.request", "XMLHttpRequest", "node:http", "undici"):
        if token in code:
            hits.append(token)
    record(not hits, f"S6 契约包代码无 AgentTransport / 无控制面调用（命中: {hits or '无'}）")

    bin_js = find_dsh()
    if bin_js is None:
        record(False, "S7 参照 dsh 不可用")
        return finish()
    if WORK.exists():
        shutil.rmtree(WORK)
    prof = WORK / "profiles" / PROFILE
    scope = prof / "node_modules" / "@worknexus"
    scope.mkdir(parents=True, exist_ok=True)
    dest = scope / "ent-core"
    try:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dest), str(BUNDLE)],
                       capture_output=True, text=True, timeout=60, check=True)
    except Exception:
        shutil.copytree(BUNDLE, dest, dirs_exist_ok=True)
    (prof / "package.json").write_text(json.dumps({
        "name": f"dsh-profile-{PROFILE}",
        "private": True,
        "dependencies": {BUNDLE_NAME: f"link:{BUNDLE.as_posix()}"},
        "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", BUNDLE_NAME], "patchReload": "live"}},
        "type": "module",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    env = dict(os.environ, DSH_HOME=str(WORK))
    run = subprocess.run(["node", str(bin_js), "--profile", PROFILE, "--dump-config"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=env, timeout=180)
    out = run.stdout or ""
    record(run.returncode == 0
           and f"# == {BUNDLE_NAME}" in out
           and "@worknexus/ent-core/skeleton" in out,
           f"S7 预置后组合树含企业段与骨架行（exit={run.returncode}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for o, _ in RESULTS if o)
    bad = sum(1 for o, _ in RESULTS if not o)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
